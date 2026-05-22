"""
kpi_calculations.py
-------------------
Computes fleet KPIs from the processed wide-format dataset
and writes a JSON summary report to reports/kpi_report.json.
"""

import pandas as pd
import numpy as np
import json
import os
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)

DATA_PATH   = "data/processed/processed_telematics.csv"
REPORT_PATH = "reports/kpi_report.json"

os.makedirs("reports", exist_ok=True)

# --------------------------------------------------
# LOAD
# --------------------------------------------------

log.info("Loading processed data...")
df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
log.info(f"Loaded {len(df):,} rows")

kpis = {}

# --------------------------------------------------
# FLEET-LEVEL KPIs
# --------------------------------------------------

kpis["fleet"] = {
    "total_records":    int(len(df)),
    "total_devices":    int(df["device_id"].nunique()),
    "date_from":        str(df["timestamp"].min().date()),
    "date_to":          str(df["timestamp"].max().date()),
    "days_covered":     int((df["timestamp"].max() - df["timestamp"].min()).days + 1),
}

# --------------------------------------------------
# ALARM KPIs
# --------------------------------------------------

alarm_dist = df["alarm_class"].value_counts().sort_index().to_dict()
alarm_labels = {0: "normal", 1: "low_risk", 2: "medium_risk",
                3: "high_risk", 4: "critical", 5: "emergency"}

kpis["alarms"] = {
    "distribution": {alarm_labels.get(int(k), str(k)): int(v) for k, v in alarm_dist.items()},
    "alarm_rate_pct": round((df["alarm_class"] > 0).mean() * 100, 2),
    "critical_plus_pct": round((df["alarm_class"] >= 4).mean() * 100, 2),
}

# --------------------------------------------------
# DRIVER SCORE KPIs
# --------------------------------------------------

if "driver_score" in df.columns:
    kpis["driver_score"] = {
        "fleet_avg":  round(df["driver_score"].mean(), 2),
        "fleet_min":  round(df["driver_score"].min(), 2),
        "fleet_max":  round(df["driver_score"].max(), 2),
        "pct_below_70": round((df["driver_score"] < 70).mean() * 100, 2),
    }

    by_device = (
        df.groupby("device_id")["driver_score"]
        .mean()
        .round(2)
        .to_dict()
    )
    kpis["driver_score"]["by_device"] = {k: float(v) for k, v in by_device.items()}
    log.info(f"Avg driver score: {kpis['driver_score']['fleet_avg']}")

# --------------------------------------------------
# SPEED KPIs
# --------------------------------------------------

speed_col = next((c for c in df.columns if "speed" in c.lower()), None)

if speed_col:
    kpis["speed"] = {
        "avg_speed_kmh":  round(df[speed_col].mean(), 2),
        "max_speed_kmh":  round(df[speed_col].max(), 2),
        "overspeed_events": int((df[speed_col] > 80).sum()),
        "overspeed_pct":  round((df[speed_col] > 80).mean() * 100, 2),
    }
    log.info(f"Max speed recorded: {kpis['speed']['max_speed_kmh']} km/h")

# --------------------------------------------------
# IDLE KPIs
# --------------------------------------------------

if "is_idle" in df.columns:
    kpis["idle"] = {
        "idle_records":   int(df["is_idle"].sum()),
        "idle_rate_pct":  round(df["is_idle"].mean() * 100, 2),
    }
    log.info(f"Idle rate: {kpis['idle']['idle_rate_pct']}%")

# --------------------------------------------------
# ENGINE KPIs
# --------------------------------------------------

rpm_col  = next((c for c in df.columns if "engine_rpm" in c), None)
load_col = next((c for c in df.columns if "calculated_engine_load" in c), None)

if rpm_col:
    kpis["engine"] = {
        "avg_rpm":       round(df[rpm_col].mean(), 2),
        "max_rpm":       round(df[rpm_col].max(), 2),
        "high_rpm_pct":  round((df[rpm_col] > 3000).mean() * 100, 2),
    }

if load_col:
    kpis.setdefault("engine", {})["avg_load_pct"] = round(df[load_col].mean(), 2)
    kpis["engine"]["high_load_pct"] = round((df[load_col] > 80).mean() * 100, 2)

# --------------------------------------------------
# TEMPERATURE KPIs
# --------------------------------------------------

coolant_col = next((c for c in df.columns if "coolant" in c), None)
if coolant_col:
    kpis["temperature"] = {
        "avg_coolant_temp_c":      round(df[coolant_col].mean(), 2),
        "overheat_events":         int((df[coolant_col] > 100).sum()),
        "overheat_pct":            round((df[coolant_col] > 100).mean() * 100, 2),
    }

# --------------------------------------------------
# PER-DEVICE SUMMARY
# --------------------------------------------------

device_summary = (
    df.groupby("device_id")
    .agg(
        records=("alarm_class", "count"),
        alarm_rate=("alarm_class", lambda x: round((x > 0).mean() * 100, 2)),
        avg_driver_score=("driver_score", "mean") if "driver_score" in df.columns else ("alarm_class", "count"),
    )
    .round(2)
    .reset_index()
    .to_dict(orient="records")
)
kpis["per_device"] = device_summary

# --------------------------------------------------
# SAVE REPORT
# --------------------------------------------------

kpis["generated_at"] = datetime.now().isoformat()

with open(REPORT_PATH, "w") as f:
    json.dump(kpis, f, indent=2)

log.info(f"KPI report saved → {REPORT_PATH}")

# Print summary to console
print("\n" + "="*50)
print("  FLEET KPI SUMMARY")
print("="*50)
print(f"  Total records   : {kpis['fleet']['total_records']:,}")
print(f"  Devices         : {kpis['fleet']['total_devices']}")
print(f"  Date range      : {kpis['fleet']['date_from']} → {kpis['fleet']['date_to']}")
print(f"  Alarm rate      : {kpis['alarms']['alarm_rate_pct']}%")
print(f"  Critical+ rate  : {kpis['alarms']['critical_plus_pct']}%")
if "driver_score" in kpis:
    print(f"  Avg driver score: {kpis['driver_score']['fleet_avg']}")
if "speed" in kpis:
    print(f"  Max speed       : {kpis['speed']['max_speed_kmh']} km/h")
    print(f"  Overspeed events: {kpis['speed']['overspeed_events']:,}")
print("="*50 + "\n")
