"""
preprocess.py
-------------
Transforms raw long-format telematics data into a wide,
analysis-ready dataset with engineered features.

Raw schema: deviceId, timeMili, timestamp, value, variable, alarmClass
Output   : one row per (deviceId, timestamp) with pivoted sensor columns
"""

import pandas as pd
import numpy as np
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)

RAW_PATH    = "data/raw/telematics.csv"
OUTPUT_PATH = "data/processed/processed_telematics.csv"

# --------------------------------------------------
# LOAD
# --------------------------------------------------

log.info("Loading raw data...")
df = pd.read_csv(RAW_PATH)
log.info(f"Loaded {len(df):,} rows | columns: {df.columns.tolist()}")

# --------------------------------------------------
# BASIC CLEANING
# --------------------------------------------------

df.columns = df.columns.str.strip()
df.drop_duplicates(inplace=True)
df.dropna(how="all", inplace=True)

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df.dropna(subset=["timestamp"], inplace=True)

# Normalise variable names
df["variable"] = df["variable"].str.strip().str.upper()

log.info(f"After dedup/clean: {len(df):,} rows")

# --------------------------------------------------
# PARSE VALUE COLUMN
# POSITION rows hold "lat,lng,altitude"; all others hold a plain float.
# --------------------------------------------------

split = df["value"].astype(str).str.split(",", expand=True)

df["value_numeric"] = pd.to_numeric(split[0], errors="coerce")
df["lng"]           = pd.to_numeric(split[1], errors="coerce")   # NaN for non-POSITION
df["altitude"]      = pd.to_numeric(split[2], errors="coerce")   # NaN for non-POSITION

# For POSITION rows rename value_numeric → lat
df["lat"] = np.where(df["variable"] == "POSITION", df["value_numeric"], np.nan)
df["value_numeric"] = np.where(df["variable"] == "POSITION", np.nan, df["value_numeric"])

# --------------------------------------------------
# PIVOT: long → wide  (one row per device × timestamp)
# --------------------------------------------------

log.info("Pivoting sensor data to wide format...")

# Keep a clean key
df["ts_key"] = df["timestamp"].dt.floor("1s")

# For POSITION rows use the coordinate columns
pos = (
    df[df["variable"] == "POSITION"]
    .groupby(["deviceId", "ts_key"])[["lat", "lng", "altitude"]]
    .first()
    .reset_index()
)

# For non-POSITION rows pivot variable → column
non_pos = df[df["variable"] != "POSITION"].copy()

pivot = non_pos.pivot_table(
    index=["deviceId", "ts_key", "alarmClass"],
    columns="variable",
    values="value_numeric",
    aggfunc="mean"
).reset_index()

pivot.columns.name = None
pivot.columns = [
    c.strip().lower().replace(" ", "_").replace("-", "_")
    if c not in ("deviceId", "ts_key", "alarmClass") else c
    for c in pivot.columns
]

# Merge position back
wide = pivot.merge(pos, on=["deviceId", "ts_key"], how="left")

log.info(f"Wide dataset: {wide.shape[0]:,} rows × {wide.shape[1]} columns")

# --------------------------------------------------
# FEATURE ENGINEERING
# --------------------------------------------------

# 1. Speed (km/h)
speed_col = next((c for c in wide.columns if "vehicle_speed" in c or c == "vehicle_speed"), None)
if speed_col:
    wide.rename(columns={speed_col: "speed_kmh"}, inplace=True)
    wide["is_idle"] = (wide["speed_kmh"] == 0).astype(int)
else:
    wide["is_idle"] = np.nan

# 2. Driver risk score  (0–100, higher = safer)
#    Based on engine load, RPM, acceleration magnitude, and alarmClass history
rpm_col   = next((c for c in wide.columns if "engine_rpm" in c), None)
load_col  = next((c for c in wide.columns if "calculated_engine_load" in c), None)
acc_x_col = next((c for c in wide.columns if "acceleration_x" in c), None)
acc_y_col = next((c for c in wide.columns if "acceleration_y" in c), None)
acc_z_col = next((c for c in wide.columns if "acceleration_z" in c), None)

score = pd.Series(100.0, index=wide.index)

if rpm_col:
    # penalise high RPM (>3000)
    score -= ((wide[rpm_col].fillna(0).clip(0, 6000) - 3000) / 3000 * 10).clip(0)

if load_col:
    # penalise engine load >80%
    score -= ((wide[load_col].fillna(0).clip(0, 100) - 80) / 20 * 10).clip(0)

if acc_x_col and acc_y_col and acc_z_col:
    magnitude = np.sqrt(
        wide[acc_x_col].fillna(0)**2 +
        wide[acc_y_col].fillna(0)**2 +
        wide[acc_z_col].fillna(0)**2
    )
    score -= (magnitude.clip(0, 20) / 20 * 15).clip(0)

# Penalise non-zero alarm class
score -= (wide["alarmClass"] * 5).clip(0, 30)

wide["driver_score"] = score.clip(0, 100).round(2)

# 3. Time features
wide["hour"]      = wide["ts_key"].dt.hour
wide["day_of_week"] = wide["ts_key"].dt.dayofweek  # 0=Mon
wide["date"]      = wide["ts_key"].dt.date.astype(str)

# 4. Throttle aggressiveness flag
throttle_col = next((c for c in wide.columns if "throttle_position" in c and "absolute" not in c), None)
if throttle_col:
    wide["aggressive_throttle"] = (wide[throttle_col].fillna(0) > 80).astype(int)

# --------------------------------------------------
# FILL REMAINING NULLS
# --------------------------------------------------

num_cols = wide.select_dtypes(include=np.number).columns
wide[num_cols] = wide[num_cols].fillna(wide[num_cols].median())

# --------------------------------------------------
# RENAME KEY COLUMNS FOR CONSISTENCY
# --------------------------------------------------

wide.rename(columns={
    "deviceId":   "device_id",
    "ts_key":     "timestamp",
    "alarmClass": "alarm_class"
}, inplace=True)

# --------------------------------------------------
# SAVE
# --------------------------------------------------

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
wide.to_csv(OUTPUT_PATH, index=False)

log.info(f"Saved processed data → {OUTPUT_PATH}")
log.info(f"Final shape: {wide.shape}")
log.info(f"Columns: {wide.columns.tolist()}")
