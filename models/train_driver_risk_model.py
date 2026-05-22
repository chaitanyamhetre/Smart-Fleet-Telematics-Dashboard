"""
train_driver_risk_model.py
--------------------------
Trains a Random Forest classifier to predict alarm class
from real telematics sensor features.

Input : data/processed/processed_telematics.csv
Output: models/driver_risk_model.pkl
        models/label_encoder.pkl
        reports/model_report.json
"""

import pandas as pd
import numpy as np
import json
import os
import logging

from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, f1_score
)
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import joblib

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)

DATA_PATH   = "data/processed/processed_telematics.csv"
MODEL_PATH  = "models/driver_risk_model.pkl"
REPORT_PATH = "reports/model_report.json"

os.makedirs("models",  exist_ok=True)
os.makedirs("reports", exist_ok=True)

# --------------------------------------------------
# LOAD
# --------------------------------------------------

log.info("Loading processed data...")
df = pd.read_csv(DATA_PATH)
log.info(f"Shape: {df.shape}")

# --------------------------------------------------
# FEATURE SELECTION
# Dynamically pick available numeric sensor columns.
# --------------------------------------------------

EXCLUDE = {
    "device_id", "timestamp", "date", "alarm_class",
    "driver_score", "lat", "lng", "altitude",
    "is_idle", "hour", "day_of_week",
}

# Core features always included if present
CORE_FEATURES = [
    "engine_rpm",
    "vehicle_speed",
    "calculated_engine_load",
    "acceleration_x",
    "acceleration_y",
    "acceleration_z",
    "engine_coolant_temperature",
    "throttle_position",
    "air_intake_temperature",
    "driver_score",
    "hour",
    "day_of_week",
    "is_idle",
    "lat",
    "lng",
]

available = [c for c in CORE_FEATURES if c in df.columns]

# Also pick up any other numeric columns not in exclude list
extra_numeric = [
    c for c in df.select_dtypes(include=np.number).columns
    if c not in EXCLUDE and c not in available
]

features = available + extra_numeric
log.info(f"Using {len(features)} features: {features}")

X = df[features].copy()
y = df["alarm_class"].copy()

log.info(f"Class distribution:\n{y.value_counts().sort_index()}")

# --------------------------------------------------
# TRAIN / TEST SPLIT
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
log.info(f"Train: {len(X_train):,}  Test: {len(X_test):,}")

# --------------------------------------------------
# PIPELINE  (imputer + model)
# --------------------------------------------------

pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("clf", RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_leaf=5,
        class_weight="balanced",   # handles class imbalance
        random_state=42,
        n_jobs=-1,
    ))
])

# --------------------------------------------------
# CROSS-VALIDATION
# --------------------------------------------------

log.info("Running 5-fold cross-validation...")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="f1_weighted", n_jobs=-1)
log.info(f"CV F1 (weighted): {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

# --------------------------------------------------
# TRAIN FINAL MODEL
# --------------------------------------------------

log.info("Training final model on full train set...")
pipeline.fit(X_train, y_train)
log.info("Training complete.")

# --------------------------------------------------
# EVALUATE
# --------------------------------------------------

predictions = pipeline.predict(X_test)

acc = accuracy_score(y_test, predictions)
f1  = f1_score(y_test, predictions, average="weighted")

print("\n" + "="*55)
print("  MODEL EVALUATION")
print("="*55)
print(f"  Accuracy (test)  : {acc:.4f}")
print(f"  F1 weighted      : {f1:.4f}")
print(f"  CV F1 mean       : {cv_scores.mean():.4f}")
print("="*55)
print("\nClassification Report:\n")
print(classification_report(y_test, predictions))

# --------------------------------------------------
# FEATURE IMPORTANCE
# --------------------------------------------------

rf_model = pipeline.named_steps["clf"]
importance_df = pd.DataFrame({
    "feature":    features,
    "importance": rf_model.feature_importances_
}).sort_values("importance", ascending=False)

print("\nTop 15 Feature Importances:")
print(importance_df.head(15).to_string(index=False))

# --------------------------------------------------
# SAVE MODEL
# --------------------------------------------------

joblib.dump(pipeline, MODEL_PATH)
joblib.dump(features, "models/feature_list.pkl")
log.info(f"Model saved → {MODEL_PATH}")

# --------------------------------------------------
# SAVE REPORT
# --------------------------------------------------

alarm_labels = {0: "normal", 1: "low_risk", 2: "medium_risk",
                3: "high_risk", 4: "critical", 5: "emergency"}

report = {
    "accuracy":         round(acc, 4),
    "f1_weighted":      round(f1, 4),
    "cv_f1_mean":       round(float(cv_scores.mean()), 4),
    "cv_f1_std":        round(float(cv_scores.std()), 4),
    "features_used":    features,
    "n_train":          int(len(X_train)),
    "n_test":           int(len(X_test)),
    "class_distribution": {
        alarm_labels.get(int(k), str(k)): int(v)
        for k, v in y.value_counts().sort_index().items()
    },
    "top_features": importance_df.head(10).to_dict(orient="records"),
}

with open(REPORT_PATH, "w") as f:
    json.dump(report, f, indent=2)

log.info(f"Report saved → {REPORT_PATH}")
