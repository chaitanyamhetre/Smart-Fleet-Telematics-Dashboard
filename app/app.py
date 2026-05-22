"""
app.py
------
Streamlit dashboard for Smart Fleet Telematics Analytics.
Run with: streamlit run app/app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="Smart Fleet Analytics",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚗 Smart Fleet Telematics Dashboard")

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

@st.cache_data
def load_data():
    df = pd.read_csv(
        "data/processed/processed_telematics.csv",
        parse_dates=["timestamp"]
    )
    return df

@st.cache_data
def load_kpi_report():
    path = "reports/kpi_report.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

df     = load_data()
report = load_kpi_report()

ALARM_LABELS = {
    0: "Normal", 1: "Low Risk", 2: "Medium Risk",
    3: "High Risk", 4: "Critical", 5: "Emergency"
}
ALARM_COLORS = {
    "Normal": "#639922", "Low Risk": "#378ADD", "Medium Risk": "#BA7517",
    "High Risk": "#D85A30", "Critical": "#E24B4A", "Emergency": "#D4537E"
}

# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------

st.sidebar.header("Filters")

devices = ["All"] + sorted(df["device_id"].unique().tolist())
selected_device = st.sidebar.selectbox("Device", devices)

if "timestamp" in df.columns:
    min_date = df["timestamp"].min().date()
    max_date = df["timestamp"].max().date()
    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
else:
    date_range = None

alarm_filter = st.sidebar.multiselect(
    "Alarm classes",
    options=list(ALARM_LABELS.values()),
    default=list(ALARM_LABELS.values())
)

# Apply filters
fdf = df.copy()
if selected_device != "All":
    fdf = fdf[fdf["device_id"] == selected_device]

if date_range and len(date_range) == 2:
    fdf = fdf[
        (fdf["timestamp"].dt.date >= date_range[0]) &
        (fdf["timestamp"].dt.date <= date_range[1])
    ]

selected_alarm_nums = [k for k, v in ALARM_LABELS.items() if v in alarm_filter]
fdf = fdf[fdf["alarm_class"].isin(selected_alarm_nums)]
fdf["alarm_label"] = fdf["alarm_class"].map(ALARM_LABELS)

if fdf.empty:
    st.warning("No data matches the selected filters.")
    st.stop()

# --------------------------------------------------
# KPI CARDS
# --------------------------------------------------

st.subheader("Fleet Overview")

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Total Records",  f"{len(fdf):,}")
k2.metric("Devices",        fdf["device_id"].nunique())
k3.metric("Alarm Rate",     f"{(fdf['alarm_class'] > 0).mean()*100:.1f}%")

if "driver_score" in fdf.columns:
    k4.metric("Avg Driver Score", f"{fdf['driver_score'].mean():.1f}")
else:
    k4.metric("Avg Driver Score", "N/A")

speed_col = next((c for c in fdf.columns if "speed" in c.lower() and "over" not in c.lower()), None)
if speed_col:
    k5.metric("Avg Speed (km/h)", f"{fdf[speed_col].mean():.1f}")
else:
    k5.metric("Critical+ Events", f"{(fdf['alarm_class'] >= 4).sum():,}")

st.divider()

# --------------------------------------------------
# ROW 1: Alarm Distribution + Timeline
# --------------------------------------------------

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Alarm Distribution")
    alarm_counts = (
        fdf["alarm_label"]
        .value_counts()
        .reindex(list(ALARM_LABELS.values()), fill_value=0)
        .reset_index()
    )
    alarm_counts.columns = ["Alarm Class", "Count"]
    alarm_counts = alarm_counts[alarm_counts["Count"] > 0]

    fig_pie = px.pie(
        alarm_counts,
        names="Alarm Class",
        values="Count",
        color="Alarm Class",
        color_discrete_map=ALARM_COLORS,
        hole=0.4
    )
    fig_pie.update_layout(margin=dict(t=20, b=20), height=320)
    st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    st.subheader("Alarm Events Over Time")
    if "timestamp" in fdf.columns:
        timeline = (
            fdf.groupby([fdf["timestamp"].dt.date, "alarm_label"])
            .size()
            .reset_index(name="count")
        )
        timeline.columns = ["date", "alarm_label", "count"]
        fig_line = px.area(
            timeline,
            x="date", y="count",
            color="alarm_label",
            color_discrete_map=ALARM_COLORS,
            labels={"count": "Events", "date": "Date", "alarm_label": "Class"},
        )
        fig_line.update_layout(margin=dict(t=20, b=20), height=320)
        st.plotly_chart(fig_line, use_container_width=True)

st.divider()

# --------------------------------------------------
# ROW 2: Driver Score + Speed Distribution
# --------------------------------------------------

col3, col4 = st.columns(2)

with col3:
    st.subheader("Driver Score by Device")
    if "driver_score" in fdf.columns:
        score_by_device = (
            fdf.groupby("device_id")["driver_score"]
            .mean()
            .reset_index()
            .sort_values("driver_score", ascending=True)
        )
        score_by_device["device_id"] = score_by_device["device_id"].str[-12:]
        fig_score = px.bar(
            score_by_device,
            x="driver_score", y="device_id",
            orientation="h",
            color="driver_score",
            color_continuous_scale=["#E24B4A", "#BA7517", "#639922"],
            labels={"driver_score": "Score", "device_id": "Device"},
        )
        fig_score.update_layout(margin=dict(t=20, b=20), height=280, coloraxis_showscale=False)
        st.plotly_chart(fig_score, use_container_width=True)
    else:
        st.info("driver_score column not found in processed data.")

with col4:
    st.subheader("Speed Distribution")
    speed_col = next((c for c in fdf.columns if "speed" in c.lower() and "over" not in c.lower()), None)
    if speed_col:
        fig_speed = px.histogram(
            fdf, x=speed_col, nbins=40,
            color_discrete_sequence=["#378ADD"],
            labels={speed_col: "Speed (km/h)", "count": "Frequency"},
        )
        fig_speed.add_vline(x=80, line_dash="dash", line_color="red", annotation_text="Speed limit 80")
        fig_speed.update_layout(margin=dict(t=20, b=20), height=280)
        st.plotly_chart(fig_speed, use_container_width=True)
    else:
        st.info("No speed column found in processed data.")

st.divider()

# --------------------------------------------------
# ROW 3: Engine RPM + Coolant Temp
# --------------------------------------------------

col5, col6 = st.columns(2)

rpm_col     = next((c for c in fdf.columns if "engine_rpm" in c), None)
coolant_col = next((c for c in fdf.columns if "coolant" in c), None)

with col5:
    st.subheader("Engine RPM Distribution")
    if rpm_col:
        fig_rpm = px.box(
            fdf, y=rpm_col, x="alarm_label",
            color="alarm_label",
            color_discrete_map=ALARM_COLORS,
            labels={rpm_col: "RPM", "alarm_label": "Alarm Class"},
        )
        fig_rpm.add_hline(y=3000, line_dash="dash", line_color="orange", annotation_text="High RPM 3000")
        fig_rpm.update_layout(margin=dict(t=20, b=20), height=300, showlegend=False)
        st.plotly_chart(fig_rpm, use_container_width=True)
    else:
        st.info("Engine RPM column not found.")

with col6:
    st.subheader("Coolant Temperature")
    if coolant_col:
        fig_cool = px.histogram(
            fdf, x=coolant_col, nbins=30,
            color_discrete_sequence=["#D85A30"],
            labels={coolant_col: "Temperature (°C)"},
        )
        fig_cool.add_vline(x=100, line_dash="dash", line_color="red", annotation_text="Overheat 100°C")
        fig_cool.update_layout(margin=dict(t=20, b=20), height=300)
        st.plotly_chart(fig_cool, use_container_width=True)
    else:
        st.info("Coolant temperature column not found.")

st.divider()

# --------------------------------------------------
# GPS MAP (if lat/lng available)
# --------------------------------------------------

if "lat" in fdf.columns and "lng" in fdf.columns:
    map_df = fdf.dropna(subset=["lat", "lng"])
    map_df = map_df[
        (map_df["lat"].between(-90, 90)) &
        (map_df["lng"].between(-180, 180)) &
        (map_df["lat"] != 0) & (map_df["lng"] != 0)
    ]

    if not map_df.empty:
        st.subheader("Vehicle GPS Tracks")
        sample = map_df.sample(min(5000, len(map_df)), random_state=42)
        fig_map = px.scatter_mapbox(
            sample,
            lat="lat", lon="lng",
            color="alarm_label",
            color_discrete_map=ALARM_COLORS,
            zoom=10,
            mapbox_style="open-street-map",
            height=450,
            labels={"alarm_label": "Alarm Class"},
        )
        fig_map.update_layout(margin=dict(t=20, b=20))
        st.plotly_chart(fig_map, use_container_width=True)
        st.divider()

# --------------------------------------------------
# PER-DEVICE TABLE
# --------------------------------------------------

st.subheader("Per-Device Summary")

agg_dict = {
    "alarm_class": ["count", lambda x: round((x > 0).mean() * 100, 1)],
}
if "driver_score" in fdf.columns:
    agg_dict["driver_score"] = "mean"
if speed_col:
    agg_dict[speed_col] = "mean"

device_table = fdf.groupby("device_id").agg(**{
    "Records":      ("alarm_class", "count"),
    "Alarm Rate %": ("alarm_class", lambda x: round((x > 0).mean() * 100, 1)),
    **( {"Avg Driver Score": ("driver_score", lambda x: round(x.mean(), 1))} if "driver_score" in fdf.columns else {}),
    **( {"Avg Speed km/h": (speed_col, lambda x: round(x.mean(), 1))} if speed_col else {}),
    "Critical+ Events": ("alarm_class", lambda x: (x >= 4).sum()),
}).reset_index()

device_table["device_id"] = device_table["device_id"].str[-16:]
st.dataframe(device_table, use_container_width=True)

st.divider()

# --------------------------------------------------
# RAW DATA EXPLORER
# --------------------------------------------------

with st.expander("🔍 Raw Data Explorer"):
    st.dataframe(
        fdf.sort_values("timestamp", ascending=False).head(500),
        use_container_width=True
    )
    st.caption(f"Showing up to 500 most recent records of {len(fdf):,} filtered rows.")

st.caption("Smart Fleet Telematics Analytics · Data: 2020-08-17 → 2020-08-24")
