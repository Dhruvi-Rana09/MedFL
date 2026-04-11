"""MedFL Monitoring Dashboard — Streamlit app for observing federated learning."""

import streamlit as st
import requests
import pandas as pd
import time

# ---------------------------------------------------------------------------
# Configuration — adjust these if running outside Docker
# ---------------------------------------------------------------------------
STORAGE_URL = "http://storage:8000"    # model-storage-service
MONITOR_URL = "http://monitor:8000"    # monitoring-service

# Allow overrides via environment for local dev
import os
STORAGE_URL = os.getenv("STORAGE_URL", STORAGE_URL)
MONITOR_URL = os.getenv("MONITOR_URL", MONITOR_URL)

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MedFL Monitoring Dashboard",
    page_icon="🏥",
    layout="wide",
)

st.title("🏥 MedFL — Federated Learning Dashboard")
st.markdown("Real-time monitoring for the distributed federated learning system.")

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def fetch_history():
    """Fetch model history from the storage service."""
    try:
        resp = requests.get(f"{STORAGE_URL}/history", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"⚠️ Could not reach Storage Service: {e}")
        return []


def fetch_logs(limit=50):
    """Fetch recent logs from the monitoring service."""
    try:
        resp = requests.get(f"{MONITOR_URL}/logs", params={"limit": limit}, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"⚠️ Could not reach Monitoring Service: {e}")
        return []


# ---------------------------------------------------------------------------
# Auto-refresh toggle
# ---------------------------------------------------------------------------
col_refresh, col_interval = st.columns([1, 1])
with col_refresh:
    auto_refresh = st.checkbox("🔄 Auto-refresh", value=True)
with col_interval:
    refresh_interval = st.slider("Refresh interval (seconds)", 3, 30, 5)

# ---------------------------------------------------------------------------
# Model History & Accuracy Chart
# ---------------------------------------------------------------------------
st.header("📊 Model Performance")

history = fetch_history()

if history:
    current_round = max(r["round_number"] for r in history)
    st.metric("Current Round", current_round)

    # Build dataframe for charting
    df = pd.DataFrame(history)

    if "accuracy" in df.columns and df["accuracy"].notna().any():
        st.subheader("Accuracy over Rounds")
        chart_df = df[["round_number", "accuracy"]].dropna(subset=["accuracy"])
        chart_df = chart_df.set_index("round_number").sort_index()
        st.line_chart(chart_df, use_container_width=True)
    else:
        st.info("ℹ️ No accuracy data reported yet. Accuracy will appear once the aggregator provides it.")

    # Show weights history table
    with st.expander("📋 Full Model History"):
        display_df = df[["round_number", "weights", "accuracy", "timestamp"]].sort_values(
            "round_number", ascending=False
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("ℹ️ No model data yet. Run an aggregation round to see results.")

# ---------------------------------------------------------------------------
# System Logs
# ---------------------------------------------------------------------------
st.header("📝 System Logs")

logs = fetch_logs(limit=100)

if logs:
    log_df = pd.DataFrame(logs)
    display_cols = ["timestamp", "event", "source"]
    if "details" in log_df.columns:
        display_cols.append("details")
    log_df = log_df[[c for c in display_cols if c in log_df.columns]]
    st.dataframe(log_df, use_container_width=True, hide_index=True)
else:
    st.info("ℹ️ No logs yet. Events will appear as the system operates.")

# ---------------------------------------------------------------------------
# Auto-refresh loop
# ---------------------------------------------------------------------------
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
