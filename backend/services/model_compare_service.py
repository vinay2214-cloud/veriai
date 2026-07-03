from typing import Dict, List

import numpy as np

# sklearn is imported lazily inside compare_models (Phase 2 startup
# optimization) so this module — pulled in by the dashboard router at startup —
# does not force sklearn to load before the app can serve health checks.
from .fairness_service import demographic_parity, equal_opportunity
from .training_service import load_data, preprocess_data


def compare_models() -> Dict[str, List[Dict]]:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    df = load_data()
    X, y, feature_names = preprocess_data(df)
    protected = np.where(df["sex"].str.strip() == "Female", 1, 0)

    X_train, X_test, y_train, y_test, p_train, p_test = train_test_split(
        X, y, protected, test_size=0.2, random_state=42
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    candidates = {
        "Logistic Regression": LogisticRegression(max_iter=500, solver="liblinear"),
        "Random Forest": RandomForestClassifier(n_estimators=120, random_state=42),
    }

    rows: List[Dict] = []
    for name, model in candidates.items():
        if name == "Random Forest":
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
        else:
            model.fit(X_train_scaled, y_train)
            y_pred = model.predict(X_test_scaled)

        dp = float(demographic_parity(y_pred, p_test))
        eo = float(equal_opportunity(y_test, y_pred, p_test))
        rows.append(
            {
                "model": name,
                "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
                "demographic_parity": round(dp, 4),
                "equal_opportunity": round(eo, 4),
                "bias_score": round((dp + eo) / 2.0, 4),
            }
        )

    rows.sort(key=lambda r: (r["bias_score"], -r["accuracy"]))
    return {"dataset": "adult.csv", "models": rows, "feature_count": len(feature_names)}
