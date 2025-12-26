"""Streamlit entrypoint for Stat Arb Dashboard."""
import streamlit as st
from datetime import datetime
from config.settings import get_settings
from config.universe import BASKETS
from data.ccxt_data import fetch_ohlcv_close_wide, trim_history, normalize_symbols, get_data_health
from ui.components import debug_panel

st.set_page_config(page_title="Stat Arb Dashboard", layout="wide")

# Load settings
settings = get_settings()

# Collect all unique tickers from all baskets
all_tickers = []
for tickers in BASKETS.values():
    all_tickers.extend(tickers)
unique_tickers = sorted(list(set(all_tickers)))

# Normalize symbols
symbols = normalize_symbols(unique_tickers)

# Refresh controls
col1, col2 = st.columns([1, 10])
with col1:
    refresh_button = st.button("🔄 Refresh data now", key="refresh_data_btn")
with col2:
    force_refresh = st.checkbox("Force refresh (ignore cache)", value=False, key="force_refresh_checkbox")

# Determine if we need to fetch/refresh
should_refresh = refresh_button or force_refresh or "prices_wide_full" not in st.session_state

# Clear cache and refetch if force refresh is checked OR refresh button pressed
if force_refresh or refresh_button:
    st.cache_data.clear()

# Fetch prices (or use cached if not refreshing)
if should_refresh:
    try:
        prices_wide_full = fetch_ohlcv_close_wide(
            exchange_id=settings.exchange_id,
            symbols=symbols,
            timeframe=settings.timeframe,
            days_fetch=settings.history_days_fetch,
        )
    except Exception as e:
        st.exception(e)
        st.stop()
    
    # Trim to display window
    prices_wide = trim_history(prices_wide_full, settings.history_days_display)
    
    # Store in session state
    st.session_state.prices_wide_full = prices_wide_full
    st.session_state.prices_wide = prices_wide
    
    # Compute and store data health
    data_health = get_data_health(prices_wide_full)
    st.session_state.data_health = data_health
    st.session_state.last_refresh_ts = datetime.now()
else:
    # Use existing data from session_state
    prices_wide_full = st.session_state.prices_wide_full
    prices_wide = st.session_state.prices_wide

st.session_state.settings = settings

# UI Display
st.title("Stat Arb Dashboard")

# Data Status box
st.write("## Data Status")

data_health = st.session_state.get("data_health", get_data_health(prices_wide_full))
last_refresh_ts = st.session_state.get("last_refresh_ts", datetime.now())

st.write(f"**Last refresh:** {last_refresh_ts.strftime('%Y-%m-%d %H:%M:%S')}")
st.write(f"**Latest candle:** {data_health['end_ts']}")
st.write(f"**Symbols fetched:** {data_health['n_cols']}")
st.write(f"**Overall missing:** {data_health['overall_missing_pct']:.2f}%")

# Top 5 worst symbols by missingness
if data_health['per_symbol_missing_top10']:
    st.write("**Top 5 worst symbols by missing data:**")
    worst_5 = data_health['per_symbol_missing_top10'][:5]
    for symbol, missing_pct in worst_5:
        st.write(f"  - {symbol}: {missing_pct:.2f}%")

# Diagnostics expander
with st.expander("Diagnostics", expanded=True):
    debug_panel(prices_wide, "prices_wide")

