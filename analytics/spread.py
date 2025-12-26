"""Spread analysis functions."""
import pandas as pd
import numpy as np


def spread_series(prices_wide: pd.DataFrame, a: str, b: str) -> pd.Series:
    """Compute spread series = log(A) - log(B).
    
    Args:
        prices_wide: DataFrame with price columns
        a: First ticker symbol (column name)
        b: Second ticker symbol (column name)
        
    Returns:
        Series with spread values (log(A) - log(B))
    """
    log_a = np.log(prices_wide[a])
    log_b = np.log(prices_wide[b])
    return log_a - log_b


def zscore(series: pd.Series, window: int) -> pd.Series:
    """Compute rolling z-score = (series - rolling_mean) / rolling_std.
    
    Args:
        series: Input series
        window: Rolling window size
        
    Returns:
        Series with z-scores
    """
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    return (series - rolling_mean) / rolling_std


def bollinger_bands(series: pd.Series, window: int, k: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute Bollinger bands = rolling_mean ± (k * rolling_std).
    
    Args:
        series: Input series
        window: Rolling window size
        k: Multiplier for standard deviation
        
    Returns:
        Tuple of (mid, upper_band, lower_band) Series
    """
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    upper_band = rolling_mean + (k * rolling_std)
    lower_band = rolling_mean - (k * rolling_std)
    return rolling_mean, upper_band, lower_band


def latest_boll_breach(series: pd.Series, upper: pd.Series, lower: pd.Series) -> bool:
    """Check if latest point breaches Bollinger bands.
    
    Args:
        series: Spread series
        upper: Upper Bollinger band series
        lower: Lower Bollinger band series
        
    Returns:
        True if latest point breaches upper or lower band
    """
    if series.empty or upper.empty or lower.empty:
        return False
    
    latest_spread = series.iloc[-1]
    latest_upper = upper.iloc[-1]
    latest_lower = lower.iloc[-1]
    
    if pd.isna(latest_spread) or pd.isna(latest_upper) or pd.isna(latest_lower):
        return False
    
    return (latest_spread > latest_upper) or (latest_spread < latest_lower)


def spread_vol(series: pd.Series, window: int) -> float:
    """Compute spread volatility as std dev of series.diff() over last window.
    
    Args:
        series: Input series
        window: Window size for calculation
        
    Returns:
        Standard deviation as float (NaN if insufficient data)
    """
    if len(series) < 2:
        return float('nan')
    
    # Compute diff (first order difference)
    diff_series = series.diff().dropna()
    
    if len(diff_series) < window:
        # Use all available data if less than window
        return float(diff_series.std()) if len(diff_series) > 1 else float('nan')
    
    # Use last window elements
    recent_diff = diff_series.tail(window)
    return float(recent_diff.std())

