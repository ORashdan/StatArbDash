"""Pair Explorer page: Scan all pairs within selected basket."""
import streamlit as st
import pandas as pd
import numpy as np
from itertools import combinations
from config.universe import BASKETS
from analytics.metrics import log_returns, pair_corr_latest
from analytics.spread import spread_series, zscore, bollinger_bands, latest_boll_breach, spread_vol
from data.ccxt_data import normalize_symbols, get_data_health
from ui.components import debug_panel

# Load data from session_state
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

# Helper function for bars since breach
def compute_bars_since_breach(breach_series: pd.Series) -> float:
    """Count bars since last breach (0 if currently breached, NaN if never breached)."""
    if breach_series.empty:
        return np.nan
    
    # Check if currently breached (last value is True)
    if breach_series.iloc[-1]:
        return 0.0
    
    # Find last True index (most recent breach)
    last_true_indices = breach_series[breach_series].index
    
    if len(last_true_indices) == 0:
        return np.nan  # Never breached
    
    last_breach_idx = last_true_indices[-1]
    current_idx = breach_series.index[-1]
    
    # Find position in index and compute difference
    try:
        last_breach_pos = breach_series.index.get_loc(last_breach_idx)
        current_pos = breach_series.index.get_loc(current_idx)
        return float(current_pos - last_breach_pos)
    except (KeyError, TypeError):
        return np.nan

# Determine active basket
if "selected_basket" in st.session_state and st.session_state.selected_basket in BASKETS:
    basket_name = st.session_state.selected_basket
else:
    basket_name = st.selectbox(
        "Select basket to explore",
        options=list(BASKETS.keys()),
        key="basket_selector_pair"
    )
    st.session_state.selected_basket = basket_name

# Get basket tickers and normalize
basket_tickers_raw = BASKETS[basket_name]
normalized_tickers = normalize_symbols(basket_tickers_raw)
valid_tickers = [t for t in normalized_tickers if t in prices_wide.columns]

# Check if we have enough tickers
if len(valid_tickers) < 2:
    st.warning(f"Basket '{basket_name}' has fewer than 2 usable tickers. Cannot compute pairs.")
    st.stop()

# Page title
st.write(f"# Pair Explorer: {basket_name}")

# Status indicator
status_parts = []
if "selected_basket" in st.session_state and st.session_state.selected_basket:
    status_parts.append(f"Basket: **{st.session_state.selected_basket}**")
if "selected_pair" in st.session_state and isinstance(st.session_state.selected_pair, tuple) and len(st.session_state.selected_pair) == 2:
    pair_a, pair_b = st.session_state.selected_pair
    status_parts.append(f"Pair: **{pair_a} / {pair_b}**")
if status_parts:
    st.info(f"📊 {' | '.join(status_parts)}")

# Controls
st.write("## Controls")

col1, col2 = st.columns(2)

with col1:
    only_opportunities = st.checkbox("Only show opportunities", value=False)
    sort_by = st.selectbox(
        "Sort by",
        options=["|z| (desc)", "Most recent breach", "Correlation (desc)", "Spread vol (desc)"],
        index=0
    )

with col2:
    min_correlation = st.slider(
        "Min correlation",
        min_value=-1.0,
        max_value=1.0,
        value=0.0,
        step=0.1
    )
    min_abs_z = st.slider(
        "Min |z|",
        min_value=0.0,
        max_value=10.0,
        value=0.0,
        step=0.1
    )

# Compute log returns
logret = log_returns(prices_wide)

# Generate all unique pairs (a < b)
pairs = []
for a, b in combinations(sorted(valid_tickers), 2):
    pairs.append((a, b))

# Compute metrics for each pair
st.write("## Pair Analysis")

pairs_data = []
for a, b in pairs:
    try:
        # Compute spread
        spread = spread_series(prices_wide, a, b)
        
        # Latest z-score
        zscore_series = zscore(spread, settings.z_window)
        latest_z = float(zscore_series.iloc[-1]) if not zscore_series.empty and not pd.isna(zscore_series.iloc[-1]) else np.nan
        
        # Bollinger bands and breach
        mid, upper_band, lower_band = bollinger_bands(spread, settings.z_window, settings.boll_k)
        breach_series = (spread > upper_band) | (spread < lower_band)
        boll_breach_latest = latest_boll_breach(spread, upper_band, lower_band)
        
        # Bars since last breach
        bars_since = compute_bars_since_breach(breach_series)
        
        # Correlation
        corr = pair_corr_latest(logret, a, b, settings.analytics_window)
        
        # Spread volatility
        spread_vol_value = spread_vol(spread, settings.analytics_window)
        
        # Opportunity flag
        opportunity = (not pd.isna(latest_z)) and (abs(latest_z) >= settings.z_entry) and bool(boll_breach_latest)
        
        pairs_data.append({
            "a": a,
            "b": b,
            "z": latest_z,
            "boll_breach": boll_breach_latest,
            "bars_since_breach": bars_since,
            "corr": corr,
            "spread_vol": spread_vol_value,
            "opportunity": opportunity,
        })
    except Exception as e:
        # Append error row with safe defaults
        pairs_data.append({
            "a": a,
            "b": b,
            "z": np.nan,
            "boll_breach": False,
            "bars_since_breach": np.nan,
            "corr": np.nan,
            "spread_vol": np.nan,
            "opportunity": False,
            "_error": str(e),
        })

if not pairs_data:
    st.write("No pairs computed.")
    st.stop()

# Create DataFrame (complete unfiltered - df_all)
df_all = pd.DataFrame(pairs_data)

# Show errors if any
if "_error" in df_all.columns and df_all["_error"].notna().any():
    with st.expander("Pair calculation errors"):
        error_df = df_all[df_all["_error"].notna()][["a", "b", "_error"]].head(20)
        st.dataframe(error_df, use_container_width=True)

# Apply filters (df_view is the filtered/sorted version)
df_view = df_all.copy()

# Filter by opportunity
if only_opportunities:
    df_view = df_view[df_view["opportunity"] == True].copy()

# Filter by min correlation
df_view = df_view[df_view["corr"] >= min_correlation].copy()

# Filter by min abs(z)
df_view = df_view[df_view["z"].abs() >= min_abs_z].copy()

# Apply sorting
if sort_by == "|z| (desc)":
    df_view["abs_z"] = df_view["z"].abs()
    df_view = df_view.sort_values("abs_z", ascending=False, na_position="last")
    df_view = df_view.drop(columns=["abs_z"])
elif sort_by == "Most recent breach":
    # Sort by bars_since_breach ascending (NaN last)
    df_view = df_view.sort_values("bars_since_breach", ascending=True, na_position="last")
elif sort_by == "Correlation (desc)":
    df_view = df_view.sort_values("corr", ascending=False, na_position="last")
elif sort_by == "Spread vol (desc)":
    df_view = df_view.sort_values("spread_vol", ascending=False, na_position="last")

# Display table
if not df_view.empty:
    # Format display columns
    display_df = df_view.copy()
    display_df = display_df.rename(columns={
        "a": "Ticker A",
        "b": "Ticker B",
        "z": "Z-Score",
        "boll_breach": "Bollinger Breach",
        "bars_since_breach": "Bars Since Breach",
        "corr": "Correlation",
        "spread_vol": "Spread Vol",
        "opportunity": "Opportunity"
    })
    st.dataframe(display_df, use_container_width=True)
else:
    st.write("No pairs match the current filters.")

# Pair Selection
st.subheader("Select pair for deep dive")

source_df = df_view
if source_df is None or source_df.empty:
    st.warning("No pairs match the current filters. Showing all pairs for selection.")
    source_df = df_all

pair_options = list(zip(source_df["a"], source_df["b"]))
if not pair_options:
    st.error("No pairs available to select. Check basket tickers and data.")
    st.stop()

labels = [f"{a} / {b}" for a, b in pair_options]
idx = st.selectbox("Pair", range(len(labels)), format_func=lambda i: labels[i], key="pair_explorer_select_idx")

a, b = pair_options[idx]
if st.button("Use this pair in Pair Deep Dive", key="pair_explorer_set_pair"):
    st.session_state.selected_pair = (a, b)
    st.session_state.selected_basket = basket_name
    st.success(f"Selected pair: {a} / {b}. Now open the Pair Deep Dive page.")

# Diagnostics
with st.expander("Diagnostics"):
    debug_panel(prices_wide, "prices_wide")
    st.write("### Usable Tickers in Basket")
    st.write(f"Total tickers: {len(valid_tickers)}")
    st.write("Tickers:", ", ".join(sorted(valid_tickers)))

