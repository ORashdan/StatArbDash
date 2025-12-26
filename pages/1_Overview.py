"""Overview page: Basket scan results."""
import streamlit as st
import pandas as pd
from config.universe import BASKETS
from analytics.scanner import scan_baskets
from ui.components import debug_panel
from config.settings import Settings
from data.ccxt_data import get_data_health

# Read from session_state
if "prices_wide" not in st.session_state or "settings" not in st.session_state:
    st.error("Data not loaded. Please run the main app first.")
    st.stop()

prices_wide = st.session_state.prices_wide
settings = st.session_state.settings

# Status caption
data_health = st.session_state.get("data_health", get_data_health(prices_wide))
last_refresh_ts = st.session_state.get("last_refresh_ts", None)
end_ts = data_health.get("end_ts", "N/A")
n_cols = data_health.get("n_cols", len(prices_wide.columns))
overall_missing_pct = data_health.get("overall_missing_pct", 0.0)
refresh_str = last_refresh_ts.strftime("%Y-%m-%d %H:%M") if last_refresh_ts else "never"
st.caption(f"Data as of {end_ts} | refreshed {refresh_str} | symbols {n_cols} | missing {overall_missing_pct:.1f}%")

# Page title
st.write("# Overview — Basket Scanner")

# Status indicator
if "selected_basket" in st.session_state and st.session_state.selected_basket:
    st.info(f"📊 Currently selected basket: **{st.session_state.selected_basket}**")

# Controls (main page, not sidebar)
col1, col2 = st.columns(2)

with col1:
    lookback_bars = st.selectbox(
        "Scanner lookback bars for top movers",
        options=[12, 24, 48, 72, 120],
        index=1,  # Default to 24
    )

with col2:
    z_entry_override = st.number_input(
        "z_entry override",
        min_value=0.0,
        max_value=10.0,
        value=float(settings.z_entry),
        step=0.1,
    )
    st.session_state.z_entry_override = z_entry_override

# Create settings object with override for z_entry
scan_settings = Settings(
    exchange_id=settings.exchange_id,
    timeframe=settings.timeframe,
    history_days_display=settings.history_days_display,
    history_days_fetch=settings.history_days_fetch,
    z_window=settings.z_window,
    analytics_window=settings.analytics_window,
    boll_k=settings.boll_k,
    z_entry=z_entry_override,
    cache_ttl_seconds=settings.cache_ttl_seconds,
)

# Run scan_baskets and display result
basket_scan_df = scan_baskets(prices_wide, BASKETS, scan_settings, lookback_bars=lookback_bars)

st.write("## Basket Scan Results")
st.dataframe(basket_scan_df)

# Basket selection
st.write("## Basket Selection")
if not basket_scan_df.empty:
    # Use baskets in the same order as the table
    basket_options = basket_scan_df["basket"].tolist()
    selected_basket = st.selectbox(
        "Select basket to explore",
        options=basket_options,
        key="basket_selectbox"
    )
    
    if st.button("Open Basket Explorer", key="open_basket_explorer_btn"):
        st.session_state.selected_basket = selected_basket
        st.success(f"Selected basket: **{selected_basket}**. Please navigate to 'Basket Explorer' page.")
        st.rerun()
else:
    st.write("No baskets available for selection.")

# Diagnostics expander
with st.expander("Diagnostics"):
    debug_panel(prices_wide, "prices_wide")
