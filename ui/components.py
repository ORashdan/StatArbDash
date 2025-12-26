"""Streamlit UI components for debugging and visualization."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def debug_panel(df: pd.DataFrame, title: str):
    """Display DataFrame debugging information panel.
    
    Args:
        df: DataFrame to inspect
        title: Title for the panel
        
    Raises:
        Stops execution if df is None or empty (via st.stop())
    """
    if df is None or df.empty:
        st.error(f"{title}: DataFrame is None or empty")
        st.stop()
        return
    
    st.write(f"### {title}")
    
    # Shape
    st.write(f"**Shape:** {df.shape[0]} rows × {df.shape[1]} columns")
    
    # Head
    st.write("**Head:**")
    st.dataframe(df.head(10))
    
    # Dtypes
    st.write("**Data Types:**")
    st.dataframe(pd.DataFrame(df.dtypes, columns=["dtype"]))
    
    # Index min/max (if datetime)
    if isinstance(df.index, pd.DatetimeIndex):
        st.write(f"**Index Range:** {df.index.min()} to {df.index.max()}")
    elif hasattr(df.index, 'min') and hasattr(df.index, 'max'):
        st.write(f"**Index Range:** {df.index.min()} to {df.index.max()}")
    
    # NaN counts (top 10)
    st.write("**NaN Counts (Top 10):**")
    nan_counts = df.isna().sum()
    nan_counts_df = pd.DataFrame(nan_counts, columns=["NaN count"]).sort_values("NaN count", ascending=False)
    st.dataframe(nan_counts_df.head(10))
    
    # Duplicate index count
    dup_count = df.index.duplicated().sum()
    st.write(f"**Duplicate Index Count:** {dup_count}")


def plot_prices(prices_wide: pd.DataFrame, a: str, b: str) -> go.Figure:
    """Plot normalized prices for two tickers (normalized to 100 at start).
    
    Args:
        prices_wide: DataFrame with price columns
        a: First ticker symbol
        b: Second ticker symbol
        
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    # Extract and normalize price series
    price_a = prices_wide[a].dropna()
    price_b = prices_wide[b].dropna()
    
    if len(price_a) > 0:
        # Normalize to 100 at first value
        norm_a = (price_a / price_a.iloc[0]) * 100
        fig.add_trace(go.Scatter(
            x=norm_a.index,
            y=norm_a.values,
            mode='lines',
            name=a,
            line=dict(color='blue')
        ))
    
    if len(price_b) > 0:
        # Normalize to 100 at first value
        norm_b = (price_b / price_b.iloc[0]) * 100
        fig.add_trace(go.Scatter(
            x=norm_b.index,
            y=norm_b.values,
            mode='lines',
            name=b,
            line=dict(color='red')
        ))
    
    fig.update_layout(
        title=f"Normalized Prices: {a} vs {b}",
        xaxis_title="Date",
        yaxis_title="Normalized Price (Base=100)",
        hovermode='x unified'
    )
    
    return fig


def plot_spread_with_bands(spread: pd.Series, mid: pd.Series, upper: pd.Series, lower: pd.Series) -> go.Figure:
    """Plot spread with Bollinger bands.
    
    Args:
        spread: Spread series
        mid: Mid band (mean) series
        upper: Upper band series
        lower: Lower band series
        
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    # Spread (main line)
    fig.add_trace(go.Scatter(
        x=spread.index,
        y=spread.values,
        mode='lines',
        name='Spread',
        line=dict(color='blue', width=2)
    ))
    
    # Mid band
    fig.add_trace(go.Scatter(
        x=mid.index,
        y=mid.values,
        mode='lines',
        name='Mid (Mean)',
        line=dict(color='gray', width=1, dash='dash')
    ))
    
    # Upper band
    fig.add_trace(go.Scatter(
        x=upper.index,
        y=upper.values,
        mode='lines',
        name='Upper Band',
        line=dict(color='red', width=1, dash='dot')
    ))
    
    # Lower band
    fig.add_trace(go.Scatter(
        x=lower.index,
        y=lower.values,
        mode='lines',
        name='Lower Band',
        line=dict(color='red', width=1, dash='dot')
    ))
    
    fig.update_layout(
        title="Spread with Bollinger Bands",
        xaxis_title="Date",
        yaxis_title="Spread",
        hovermode='x unified'
    )
    
    return fig


def plot_zscore(z: pd.Series) -> go.Figure:
    """Plot z-score over time with reference lines.
    
    Args:
        z: Z-score series
        
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    # Z-score line
    fig.add_trace(go.Scatter(
        x=z.index,
        y=z.values,
        mode='lines',
        name='Z-Score',
        line=dict(color='blue', width=2)
    ))
    
    # Reference lines at +2, -2, 0
    if len(z) > 0:
        fig.add_hline(y=2, line_dash="dash", line_color="red", annotation_text="+2")
        fig.add_hline(y=-2, line_dash="dash", line_color="red", annotation_text="-2")
        fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="0")
    
    fig.update_layout(
        title="Z-Score",
        xaxis_title="Date",
        yaxis_title="Z-Score",
        hovermode='x unified'
    )
    
    return fig


def plot_rolling_corr(corr: pd.Series) -> go.Figure:
    """Plot rolling correlation over time.
    
    Args:
        corr: Rolling correlation series
        
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=corr.index,
        y=corr.values,
        mode='lines',
        name='Rolling Correlation',
        line=dict(color='green', width=2)
    ))
    
    # Reference line at 0
    if len(corr) > 0:
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
    
    fig.update_layout(
        title="Rolling Correlation",
        xaxis_title="Date",
        yaxis_title="Correlation",
        yaxis=dict(range=[-1, 1]),
        hovermode='x unified'
    )
    
    return fig

