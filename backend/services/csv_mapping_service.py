"""CSV preview + mapping utilities for dataset audits."""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

VALID_ROLES = {"target", "protected_attribute", "feature", "ignore"}


def read_csv_bytes(content: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(content))


def _clean_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .replace({"": np.nan, "nan": np.nan, "None": np.nan, "null": np.nan, "NaN": np.nan})
    )


def _json_safe(values: List[Any]) -> List[Any]:
    safe: List[Any] = []
    for value in values:
        if pd.isna(value):
            continue
        if isinstance(value, (np.generic,)):
            safe.append(value.item())
        else:
            safe.append(value)
    return safe


def infer_csv_schema(df: pd.DataFrame) -> Dict[str, Any]:
    columns: List[Dict[str, Any]] = []
    column_names = df.columns.tolist()
    last_col = column_names[-1] if column_names else None

    for col in column_names:
        raw = df[col]
        cleaned = _clean_series(raw)
        unique_vals = cleaned.dropna().unique().tolist()
        unique_count = len(unique_vals)
        numeric_col = is_numeric_dtype(raw)

        if unique_count <= 2 and unique_count > 0:
            inferred_type = "binary"
        elif (not numeric_col) and unique_count <= 10 and unique_count > 0:
            inferred_type = "categorical"
        elif numeric_col:
            inferred_type = "numeric"
        else:
            inferred_type = "text"

        if inferred_type == "binary":
            suggested_role = "target" if col == last_col else "protected_attribute"
        elif inferred_type == "categorical":
            suggested_role = "protected_attribute"
        else:
            suggested_role = "feature"

        payload: Dict[str, Any] = {
            "name": col,
            "type": inferred_type,
            "suggested_role": suggested_role,
        }
        if inferred_type in {"binary", "categorical"}:
            payload["unique_values"] = _json_safe(unique_vals[:10])
        columns.append(payload)

    return {
        "columns": columns,
        "preview_rows": df.head(5).replace({np.nan: None}).to_dict(orient="records"),
        "row_count": int(len(df)),
    }


def normalize_mapping(mapping: Dict[str, Any], columns: List[str]) -> Dict[str, str]:
    roles: Dict[str, str] = {}

    if isinstance(mapping.get("roles"), dict):
        candidate = mapping["roles"]
    elif isinstance(mapping.get("columns"), list):
        candidate = {item.get("name"): item.get("role") for item in mapping["columns"] if isinstance(item, dict)}
    else:
        candidate = {k: v for k, v in mapping.items() if k in columns and isinstance(v, str)}

    for col in columns:
        role = candidate.get(col, "feature")
        if role not in VALID_ROLES:
            role = "feature"
        roles[col] = role
    return roles


def _encode_binary(series: pd.Series) -> Tuple[np.ndarray, List[str]]:
    clean = _clean_series(series).fillna("missing")
    encoded, uniques = pd.factorize(clean.astype(str), sort=True)
    classes = [str(c) for c in uniques.tolist()]
    return encoded.astype(float), classes


def build_mapped_dataset(df: pd.DataFrame, mapping: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if df.empty:
        raise ValueError("CSV is empty.")

    columns = df.columns.tolist()
    roles = normalize_mapping(mapping, columns)

    targets = [c for c, r in roles.items() if r == "target"]
    protecteds = [c for c, r in roles.items() if r == "protected_attribute"]
    ignored = [c for c, r in roles.items() if r == "ignore"]
    selected_features = [c for c, r in roles.items() if r == "feature"]

    if len(targets) != 1:
        raise ValueError("Exactly one target column is required.")
    if len(protecteds) > 1:
        raise ValueError("Only one protected attribute is supported right now.")

    target_col = targets[0]
    protected_col = protecteds[0] if protecteds else None
    feature_cols = [c for c in selected_features if c not in ignored and c != target_col]

    if protected_col and protected_col not in feature_cols:
        feature_cols = [protected_col] + feature_cols
    if not feature_cols:
        raise ValueError("At least one feature column is required.")

    X_frames: List[pd.DataFrame] = []
    encoded_feature_names: List[str] = []
    protected_classes: Optional[List[str]] = None

    for col in feature_cols:
        series = df[col]

        if col == protected_col:
            encoded, classes = _encode_binary(series)
            if len(classes) != 2:
                raise ValueError(f"Protected attribute '{col}' must have exactly 2 values.")
            protected_classes = classes
            X_frames.append(pd.DataFrame({col: encoded}))
            encoded_feature_names.append(col)
            continue

        if is_numeric_dtype(series):
            numeric_series = pd.to_numeric(series, errors="coerce")
            fill_value = float(numeric_series.median()) if not numeric_series.dropna().empty else 0.0
            X_frames.append(pd.DataFrame({col: numeric_series.fillna(fill_value).astype(float)}))
            encoded_feature_names.append(col)
            continue

        clean = _clean_series(series).fillna("missing")
        unique_count = clean.nunique(dropna=True)

        if unique_count <= 2:
            encoded, _ = _encode_binary(clean)
            X_frames.append(pd.DataFrame({col: encoded}))
            encoded_feature_names.append(col)
        else:
            dummies = pd.get_dummies(clean, prefix=col, prefix_sep="__", dtype=float)
            X_frames.append(dummies)
            encoded_feature_names.extend(dummies.columns.tolist())

    X_df = pd.concat(X_frames, axis=1)
    X_df = X_df.replace([np.inf, -np.inf], 0).fillna(0)

    y_encoded, target_classes = _encode_binary(df[target_col])
    if len(target_classes) != 2:
        raise ValueError(f"Target column '{target_col}' must have exactly 2 values.")

    if protected_col is None:
        protected_index = 0
    else:
        protected_index = encoded_feature_names.index(protected_col)

    dataset_payload = {
        "features": X_df.astype(float).values.tolist(),
        "labels": y_encoded.astype(float).tolist(),
        "feature_names": encoded_feature_names,
        "protected_index": protected_index,
    }

    mapping_payload = {
        "roles": roles,
        "target_column": target_col,
        "protected_attribute": protected_col,
        "ignored_columns": ignored,
        "encoded_feature_names": encoded_feature_names,
        "target_classes": target_classes,
        "protected_classes": protected_classes,
    }
    return dataset_payload, mapping_payload
