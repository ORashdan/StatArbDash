"""Pair Deep Dive page: Detailed analysis of selected pair."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from itertools import combinations
from config.universe import BASKETS
from analytics.metrics import log_returns, rolling_corr
from analytics.spread import spread_series, zscore, bollinger_bands, spread_vol
from data.ccxt_data import normalize_symbols, get_data_health
from ui.components import debug_panel, plot_prices, plot_spread_with_bands, plot_rolling_corr

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

# Pair Selection Logic
if "selected_pair" in st.session_state and isinstance(st.session_state.selected_pair, tuple) and len(st.session_state.selected_pair) == 2:
    a, b = st.session_state.selected_pair
else:
    # Show selectboxes for basket and pair
    basket_names = list(BASKETS.keys())
    default_basket_idx = 0
    if "selected_basket" in st.session_state and st.session_state.selected_basket in basket_names:
        default_basket_idx = basket_names.index(st.session_state.selected_basket)
    
    selected_basket_name = st.selectbox(
        "Select basket",
        options=basket_names,
        index=default_basket_idx,
        key="deep_dive_basket_select"
    )
    st.session_state.selected_basket = selected_basket_name
    
    # Get pairs from selected basket
    basket_tickers_raw = BASKETS[selected_basket_name]
    normalized_tickers = normalize_symbols(basket_tickers_raw)
    valid_tickers = [t for t in normalized_tickers if t in prices_wide.columns]
    
    pairs_list = []
    for ticker_a, ticker_b in combinations(sorted(valid_tickers), 2):
        pairs_list.append((ticker_a, ticker_b))
    
    if not pairs_list:
        st.error(f"No valid pairs found in basket '{selected_basket_name}'. Please select a different basket.")
        st.stop()
    
    pair_labels = [f"{pair_a} / {pair_b}" for pair_a, pair_b in pairs_list]
    selected_pair_idx = st.selectbox(
        "Select pair",
        options=range(len(pair_labels)),
        format_func=lambda i: pair_labels[i],
        key="deep_dive_pair_select"
    )
    
    a, b = pairs_list[selected_pair_idx]
    st.session_state.selected_pair = (a, b)

# Validate pair exists in prices_wide
if a not in prices_wide.columns or b not in prices_wide.columns:
    available_cols = list(prices_wide.columns)[:20]
    st.error(f"Pair symbols not found in prices_wide. Available columns (first 20): {', '.join(available_cols)}")
    st.stop()

# Check if enough rows for z_window
if len(prices_wide) < settings.z_window:
    st.warning(f"Warning: Only {len(prices_wide)} rows available, but z_window requires {settings.z_window} rows. Results may be incomplete.")

# Page title
st.write(f"# Pair Deep Dive: {a} / {b}")

# Status indicator and clear button
status_parts = []
if "selected_basket" in st.session_state and st.session_state.selected_basket:
    status_parts.append(f"Basket: **{st.session_state.selected_basket}**")
status_parts.append(f"Pair: **{a} / {b}**")
st.info(f"📊 {' | '.join(status_parts)}")

if st.button("Clear selected pair", key="clear_pair_btn"):
    if "selected_pair" in st.session_state:
        del st.session_state.selected_pair
    st.success("Selected pair cleared.")
    st.rerun()

# Use full history for calculations, trimmed for display
prices_calc = st.session_state.get("prices_wide_full", prices_wide)

# Compute log returns from calculation data
logret_calc = log_returns(prices_calc)

# Compute series from calculation data
spread = spread_series(prices_calc, a, b)
z = zscore(spread, settings.z_window)
mid, upper, lower = bollinger_bands(spread, settings.z_window, settings.boll_k)

# Compute rolling correlation with min_periods
logret_clean = logret_calc[[a, b]].dropna()
corr = logret_calc[a].rolling(
    settings.analytics_window, 
    min_periods=max(20, settings.analytics_window // 2)
).corr(logret_calc[b])

# Determine display window start
display_start = prices_wide.index.min()

# Slice series to display window for plotting
spread_plot = spread[spread.index >= display_start]
z_plot = z[z.index >= display_start]
mid_plot = mid[mid.index >= display_start]
upper_plot = upper[upper.index >= display_start]
lower_plot = lower[lower.index >= display_start]
corr_plot = corr[corr.index >= display_start]

# Compute volatilities (for reference, not displayed)
vol_a = logret_calc[a].rolling(window=settings.analytics_window).std()
vol_b = logret_calc[b].rolling(window=settings.analytics_window).std()

# Spread volatility
spread_vol_series = spread.diff().rolling(window=settings.analytics_window).std()

# Top Stats Row
st.write("## Key Metrics")

latest_z = float(z.iloc[-1]) if not z.empty and not pd.isna(z.iloc[-1]) else np.nan
latest_spread = float(spread.iloc[-1]) if not spread.empty and not pd.isna(spread.iloc[-1]) else np.nan
latest_upper = float(upper.iloc[-1]) if not upper.empty and not pd.isna(upper.iloc[-1]) else np.nan
latest_lower = float(lower.iloc[-1]) if not lower.empty and not pd.isna(lower.iloc[-1]) else np.nan
latest_corr = float(corr.iloc[-1]) if not corr.empty and not pd.isna(corr.iloc[-1]) else np.nan

# Determine bollinger breach
boll_breach = False
if not pd.isna(latest_spread) and not pd.isna(latest_upper) and not pd.isna(latest_lower):
    boll_breach = (latest_spread > latest_upper) or (latest_spread < latest_lower)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Latest Z-Score", f"{latest_z:.3f}" if not pd.isna(latest_z) else "N/A")

with col2:
    st.metric("Latest Spread", f"{latest_spread:.6f}" if not pd.isna(latest_spread) else "N/A")

with col3:
    st.metric("Bollinger Breach", "Yes" if boll_breach else "No")

with col4:
    st.metric("Correlation (240-bar)", f"{latest_corr:.3f}" if not pd.isna(latest_corr) else "N/A")

# Charts
st.write("## Charts")

# Price chart
st.write("### Normalized Prices")
price_fig = plot_prices(prices_wide, a, b)
st.plotly_chart(price_fig, use_container_width=True)

# Spread chart with bands
st.write("### Spread with Bollinger Bands")
spread_fig = plot_spread_with_bands(spread_plot, mid_plot, upper_plot, lower_plot)
st.plotly_chart(spread_fig, use_container_width=True)

# Z-score chart with reference lines
st.write("### Z-Score")
z_fig = go.Figure()
z_fig.add_trace(go.Scatter(
    x=z_plot.index,
    y=z_plot.values,
    mode='lines',
    name='Z-Score',
    line=dict(color='blue', width=2)
))
# Reference lines
if len(z_plot) > 0:
    z_fig.add_hline(y=settings.z_entry, line_dash="dash", line_color="red", annotation_text=f"+{settings.z_entry}")
    z_fig.add_hline(y=-settings.z_entry, line_dash="dash", line_color="red", annotation_text=f"-{settings.z_entry}")
    z_fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="0")
z_fig.update_layout(
    title="Z-Score",
    xaxis_title="Date",
    yaxis_title="Z-Score",
    hovermode='x unified'
)
st.plotly_chart(z_fig, use_container_width=True)

# Rolling correlation chart
st.write("### Rolling Correlation")
corr_fig = plot_rolling_corr(corr_plot)
st.plotly_chart(corr_fig, use_container_width=True)

# Diagnostics for correlation
st.write(f"**corr non-NaN points:** {int(corr_plot.notna().sum())}")
st.write(f"**paired rows for corr:** {int(logret_clean.shape[0])}")

# Recent Values Table
st.write("## Recent Values (Last 20 Rows)")

recent_data = pd.DataFrame({
    "spread": spread_plot.tail(20),
    "z": z_plot.tail(20),
    "upper": upper_plot.tail(20),
    "lower": lower_plot.tail(20),
})

st.dataframe(recent_data, use_container_width=True)

# Diagnostics
with st.expander("Diagnostics"):
    debug_panel(prices_wide, "prices_wide")
    
    st.write("### Pair-Specific Diagnostics")
    
    # Missing pct for a and b
    missing_pct_a = float((prices_wide[a].isna().sum() / len(prices_wide)) * 100) if len(prices_wide) > 0 else 0.0
    missing_pct_b = float((prices_wide[b].isna().sum() / len(prices_wide)) * 100) if len(prices_wide) > 0 else 0.0
    
    st.write(f"**Missing data:**")
    st.write(f"- {a}: {missing_pct_a:.2f}%")
    st.write(f"- {b}: {missing_pct_b:.2f}%")
    
    # Last timestamp
    if len(prices_wide) > 0:
        st.write(f"**Last timestamp:** {prices_wide.index.max()}")

