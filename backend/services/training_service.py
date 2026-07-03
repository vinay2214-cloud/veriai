"""Training / retraining service.
Provides real model training pipeline for the Adult dataset.
Includes load caching, preprocessing, SGD online training, evaluation, bias mitigation, saving, and loading.
"""
import os
import pandas as pd
import numpy as np
from typing import Dict, Any

# NOTE (Phase 2 — startup optimization): sklearn and joblib are heavy imports
# (~90 MB RSS, ~0.9 s import). They are only needed when a model is trained,
# loaded, or scored — never at process startup. Importing them lazily inside
# the functions that use them keeps the FastAPI cold-start fast and the idle
# health-check memory footprint low, without changing any behavior.
from ..config import DB_PATH
import aiosqlite

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "adult.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "model.pkl")

# Adult income column indices / features based on standard UCI dataset
COLUMNS = [
    "age", "workclass", "fnlwgt", "education", "education-num", 
    "marital-status", "occupation", "relationship", "race", "sex", 
    "capital-gain", "capital-loss", "hours-per-week", "native-country", "income"
]

# GLOBALS CACHE
# These will be loaded at app startup to dramatically improve response times.
APP_STATE = {
    "model": None,
    "scaler": None,
    "feature_names": None,
    "df_cache": None,
    "X_cache": None,
    "y_cache": None
}

def load_data(path: str = DATA_PATH) -> pd.DataFrame:
    """Load the Adult dataset from CSV. Cache it aggressively."""
    if APP_STATE["df_cache"] is not None:
        return APP_STATE["df_cache"]
        
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found at {path}")
    
    df = pd.read_csv(path, names=COLUMNS, skipinitialspace=True, engine="python")
    # Drop rows with missing values ('?')
    df.replace("?", pd.NA, inplace=True)
    df.dropna(inplace=True)
    
    APP_STATE["df_cache"] = df
    return df

def preprocess_data(df: pd.DataFrame):
    """Preprocess the adult dataset."""
    if APP_STATE["X_cache"] is not None and APP_STATE["y_cache"] is not None and APP_STATE["feature_names"] is not None:
         return APP_STATE["X_cache"], APP_STATE["y_cache"], APP_STATE["feature_names"]

    X = df.drop("income", axis=1)
    y = df["income"].apply(lambda x: 1 if ">50K" in x else 0).values

    # One-hot encode categorical features
    X = pd.get_dummies(X, drop_first=True)
    feature_names = list(X.columns)
    
    APP_STATE["X_cache"] = X.values
    APP_STATE["y_cache"] = y
    APP_STATE["feature_names"] = feature_names
    
    return X.values, y, feature_names

def train_model(sample_weight: np.ndarray = None) -> Dict[str, Any]:
    """Train a SGDClassifier model on the Adult dataset and save it."""
    try:
        import joblib
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import SGDClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score

        df = load_data()
        X, y, feature_names = preprocess_data(df)
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Handle weights for the split if provided
        weights_train = None
        if sample_weight is not None:
             _w_X_train, _w_X_test, weights_train, _w_test = train_test_split(
                 X, sample_weight, test_size=0.2, random_state=42)

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # SGD provides logarithmic loss (LogisticRegression) and handles partial_fit natively
        clf = SGDClassifier(loss='log_loss', penalty='l2', random_state=42, max_iter=1000)
        clf.fit(X_train_scaled, y_train, sample_weight=weights_train)
        
        # Evaluate
        y_pred = clf.predict(X_test_scaled)
        acc = accuracy_score(y_test, y_pred)
        
        # Cache active memory pointers to eliminate reloading
        APP_STATE["model"] = clf
        APP_STATE["scaler"] = scaler
        APP_STATE["feature_names"] = feature_names

        # Save model to disk
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump({"model": clf, "scaler": scaler, "feature_names": feature_names}, MODEL_PATH)

        return {
            "status": "success",
            "accuracy": float(acc),
            "message": "Model trained and saved."
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def _load_model_dict() -> Dict[str, Any]:
    """Internal helper to load the model and feature names together."""
    if APP_STATE["model"] and APP_STATE["scaler"] and APP_STATE["feature_names"]:
        return {"model": APP_STATE["model"], "scaler": APP_STATE["scaler"], "feature_names": APP_STATE["feature_names"]}
        
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model not found. Please train it first.")

    import joblib
    state = joblib.load(MODEL_PATH)
    APP_STATE["model"] = state["model"]
    APP_STATE["scaler"] = state["scaler"]
    APP_STATE["feature_names"] = state["feature_names"]
    
    return state

def get_live_model():
    """Retrieve raw model and scaler"""
    state = _load_model_dict()
    return state["model"], state["scaler"]

def load_model():
    """Backward-compatible alias. Returns the model pipeline object."""
    model, _scaler = get_live_model()
    return model

def predict(input_features: np.ndarray) -> np.ndarray:
    """Predict using the loaded model."""
    model, scaler = get_live_model()
    X_scaled = scaler.transform(input_features)
    return model.predict(X_scaled)

def predict_proba(input_features: np.ndarray) -> np.ndarray:
    """Predict probabilities using the loaded model."""
    model, scaler = get_live_model()
    X_scaled = scaler.transform(input_features)
    return model.predict_proba(X_scaled)

async def check_retrain_trigger() -> bool:
    """Check if feedback volume mandates a retrain."""
    # (Optional) keep original feedback checking concept
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM feedback") as cur:
                count = (await cur.fetchone())[0]
        return count > 0 and count % 5 == 0  # Re-trigger mini batches dynamically for effect
    except Exception:
        return False
