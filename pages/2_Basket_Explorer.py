"""Basket Explorer page: Detailed analysis of selected basket."""
import streamlit as st
import pandas as pd
import numpy as np
from itertools import combinations
from config.universe import BASKETS
from analytics.metrics import log_returns, basket_return, pair_corr_latest
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
        key="basket_selector"
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
st.write(f"# Basket Explorer: {basket_name}")

# Status indicator
if "selected_pair" in st.session_state and isinstance(st.session_state.selected_pair, tuple) and len(st.session_state.selected_pair) == 2:
    pair_a, pair_b = st.session_state.selected_pair
    st.info(f"📊 Currently selected pair: **{pair_a} / {pair_b}**")

# Compute log returns
logret = log_returns(prices_wide)

# Compute opportunity count first (needed for metrics)
pairs = []
for a, b in combinations(sorted(valid_tickers), 2):
    pairs.append((a, b))

opp_count = 0
for a, b in pairs:
    try:
        spread = spread_series(prices_wide, a, b)
        zscore_series = zscore(spread, settings.z_window)
        mid, upper_band, lower_band = bollinger_bands(spread, settings.z_window, settings.boll_k)
        latest_breach = latest_boll_breach(spread, upper_band, lower_band)
        
        if not zscore_series.empty and not pd.isna(zscore_series.iloc[-1]):
            latest_z = float(zscore_series.iloc[-1])
            if abs(latest_z) >= settings.z_entry and latest_breach:
                opp_count += 1
    except Exception:
        continue

# Basket Summary Metrics
st.write("## Basket Summary")

# Basket return (last 24 bars)
basket_ret_24 = basket_return(logret[valid_tickers].tail(24), valid_tickers)
basket_return_24_pct = float(basket_ret_24.sum() * 100) if not basket_ret_24.empty else 0.0

# Basket volatility
basket_ret = basket_return(logret, valid_tickers)
recent_basket_ret = basket_ret.tail(settings.analytics_window) if len(basket_ret) >= settings.analytics_window else basket_ret
basket_vol_value = float(recent_basket_ret.std()) if len(recent_basket_ret) > 1 else 0.0

# Number of tickers
n_tickers = len(valid_tickers)

# Create metric cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Basket Return (24 bars)", f"{basket_return_24_pct:.2f}%")

with col2:
    st.metric("Basket Volatility", f"{basket_vol_value:.4f}")

with col3:
    st.metric("Number of Tickers", n_tickers)

with col4:
    st.metric("Opportunity Count", opp_count)

# Members Table
st.write("## Basket Members")

members_data = []
for ticker in valid_tickers:
    # return_24: percent (sum of log returns over last 24 bars)
    ticker_logret = logret[ticker].tail(24)
    return_24_pct = float(ticker_logret.sum() * 100) if not ticker_logret.empty else 0.0
    
    # vol_240: std dev of log returns over last analytics_window bars
    ticker_logret_240 = logret[ticker].tail(settings.analytics_window) if len(logret[ticker]) >= settings.analytics_window else logret[ticker]
    vol_240_value = float(ticker_logret_240.std()) if len(ticker_logret_240) > 1 else 0.0
    
    # missing_pct: percent missing in last 10d window
    last_10d_bars = min(len(prices_wide), settings.history_days_display * 24)  # Approximate bars in 10d for 1h timeframe
    ticker_prices_10d = prices_wide[ticker].tail(last_10d_bars)
    missing_pct = float((ticker_prices_10d.isna().sum() / len(ticker_prices_10d)) * 100) if len(ticker_prices_10d) > 0 else 100.0
    
    members_data.append({
        "ticker": ticker,
        "return_24": return_24_pct,
        "vol_240": vol_240_value,
        "missing_pct": missing_pct,
    })

members_df = pd.DataFrame(members_data)
if not members_df.empty:
    members_df["abs_return_24"] = members_df["return_24"].abs()
    members_df = members_df.sort_values("abs_return_24", ascending=False)
    members_df = members_df.drop(columns=["abs_return_24"])
    members_df = members_df.rename(columns={
        "return_24": "Return (24 bars, %)",
        "vol_240": "Volatility (240 bars)",
        "missing_pct": "Missing (10d, %)"
    })
    st.dataframe(members_df, use_container_width=True)

# Opportunities Table
st.write("## Pair Opportunities")

opportunities_data = []
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
        latest_breach = latest_boll_breach(spread, upper_band, lower_band)
        
        # Bars since last breach
        bars_since = compute_bars_since_breach(breach_series)
        
        # Correlation (240-bar)
        corr_value = pair_corr_latest(logret, a, b, settings.analytics_window)
        
        # Spread volatility (240-bar)
        spread_vol_value = spread_vol(spread, settings.analytics_window)
        
        # Opportunity flag
        is_opportunity = not np.isna(latest_z) and abs(latest_z) >= settings.z_entry and latest_breach
        
        opportunities_data.append({
            "a": a,
            "b": b,
            "z": latest_z,
            "boll_breach": latest_breach,
            "bars_since_breach": bars_since,
            "corr": corr_value,
            "spread_vol": spread_vol_value,
            "opportunity": is_opportunity,
        })
    except Exception:
        continue  # Skip pairs that fail

# Always define source_df_for_selection for pair selection
source_df_for_selection = pd.DataFrame()

if opportunities_data:
    opp_df = pd.DataFrame(opportunities_data)
    
    # Filter checkbox
    show_all = st.checkbox("Show all pairs", value=False)
    
    # Filter to opportunities only if checkbox is unchecked
    if not show_all:
        opp_df = opp_df[opp_df["opportunity"] == True].copy()
    
    if not opp_df.empty:
        # Sort by abs(z) desc
        opp_df["abs_z"] = opp_df["z"].abs()
        opp_df = opp_df.sort_values("abs_z", ascending=False)
        opp_df = opp_df.drop(columns=["abs_z"])
        
        # Format display
        display_df = opp_df.copy()
        display_df = display_df.rename(columns={
            "a": "Ticker A",
            "b": "Ticker B",
            "z": "Z-Score",
            "boll_breach": "Bollinger Breach",
            "bars_since_breach": "Bars Since Breach",
            "corr": "Correlation (240)",
            "spread_vol": "Spread Vol (240)",
            "opportunity": "Opportunity"
        })
        st.dataframe(display_df, use_container_width=True)
        
        # Pair Selection (always show, using filtered df)
        source_df_for_selection = display_df
    else:
        st.write("No pairs found matching the criteria.")
        # Fall back to all pairs for selection
        all_pairs_df = pd.DataFrame(opportunities_data)
        if not all_pairs_df.empty:
            source_df_for_selection = all_pairs_df.rename(columns={
                "a": "Ticker A",
                "b": "Ticker B",
            })
else:
    st.write("No pair opportunities computed.")

# Pair Selection section (always visible if we have pairs)
if not source_df_for_selection.empty and "Ticker A" in source_df_for_selection.columns:
    st.write("## Select pair for deep dive")
    
    # Create pair labels for selectbox
    pair_options = [f"{row['Ticker A']} / {row['Ticker B']}" for _, row in source_df_for_selection.iterrows()]
    pair_dict = {f"{row['Ticker A']} / {row['Ticker B']}": (row['Ticker A'], row['Ticker B']) for _, row in source_df_for_selection.iterrows()}
    
    if pair_options:
        selected_pair_label = st.selectbox(
            "Select pair",
            options=pair_options,
            key="pair_selector_basket_explorer"
        )
        
        if st.button("Set pair for deep dive", key="set_pair_btn_basket_explorer"):
            if selected_pair_label in pair_dict:
                a, b = pair_dict[selected_pair_label]
                st.session_state.selected_pair = (a, b)
                st.session_state.selected_basket = basket_name
                st.success(f"Selected pair: **{a} / {b}**. Please navigate to 'Pair Deep Dive' page.")
                st.rerun()

# Diagnostics
with st.expander("Diagnostics"):
    debug_panel(prices_wide, "prices_wide")

