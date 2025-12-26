"""Scan baskets and pairs for statistical arbitrage opportunities."""
import pandas as pd
import numpy as np
from itertools import combinations
from analytics.metrics import log_returns, basket_return, basket_vol, pair_corr_latest
from analytics.spread import spread_series, zscore, bollinger_bands, latest_boll_breach, spread_vol
from data.ccxt_data import normalize_symbols


def _compute_spread(prices_wide: pd.DataFrame, a: str, b: str) -> pd.Series:
    """Compute log spread = log(price_a) - log(price_b).
    
    Args:
        prices_wide: DataFrame with price columns
        a: First ticker symbol
        b: Second ticker symbol
        
    Returns:
        Series with log spread
    """
    log_a = np.log(prices_wide[a])
    log_b = np.log(prices_wide[b])
    return log_a - log_b


def _compute_zscore(spread: pd.Series, window: int) -> pd.Series:
    """Compute z-score of spread = (spread - rolling_mean) / rolling_std.
    
    Args:
        spread: Series with spread values
        window: Rolling window size
        
    Returns:
        Series with z-scores
    """
    rolling_mean = spread.rolling(window=window).mean()
    rolling_std = spread.rolling(window=window).std()
    return (spread - rolling_mean) / rolling_std


def _compute_bollinger_bands(spread: pd.Series, window: int, k: float) -> tuple[pd.Series, pd.Series]:
    """Compute Bollinger bands = rolling_mean ± (k * rolling_std).
    
    Args:
        spread: Series with spread values
        window: Rolling window size
        k: Multiplier for standard deviation
        
    Returns:
        Tuple of (upper_band, lower_band) Series
    """
    rolling_mean = spread.rolling(window=window).mean()
    rolling_std = spread.rolling(window=window).std()
    upper_band = rolling_mean + (k * rolling_std)
    lower_band = rolling_mean - (k * rolling_std)
    return upper_band, lower_band


def _detect_bollinger_breach(spread: pd.Series, upper_band: pd.Series, lower_band: pd.Series) -> pd.Series:
    """Detect when spread crosses outside Bollinger bands.
    
    Args:
        spread: Series with spread values
        upper_band: Series with upper Bollinger band
        lower_band: Series with lower Bollinger band
        
    Returns:
        Boolean Series: True when spread is outside bands
    """
    return (spread > upper_band) | (spread < lower_band)


def _compute_bars_since_breach(breach_series: pd.Series) -> float:
    """Count bars since last breach (0 if currently breached, NaN if never breached).
    
    Args:
        breach_series: Boolean Series with breach indicators
        
    Returns:
        Number of bars since last breach, or NaN if never breached
    """
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


def scan_baskets(prices_wide: pd.DataFrame, baskets: dict[str, list[str]], settings, lookback_bars: int = 24) -> pd.DataFrame:
    """Scan baskets and return summary metrics.
    
    Args:
        prices_wide: DataFrame with datetime index and price columns
        baskets: Dictionary mapping basket names to lists of ticker symbols (raw format)
        settings: Settings object with analytics_window, z_entry, z_window, boll_k
        lookback_bars: Number of bars to use for top movers calculation (default 24)
        
    Returns:
        DataFrame with columns: basket, n_tickers, basket_vol, opp_count, top_movers
        Sorted by basket_vol desc, then opp_count desc
    """
    logret = log_returns(prices_wide)
    results = []
    
    for basket_name, tickers_raw in baskets.items():
        # Convert tickers using normalize_symbols to match prices_wide column names
        normalized_tickers = normalize_symbols(tickers_raw)
        
        # Filter to only tickers that exist in prices_wide
        valid_tickers = [t for t in normalized_tickers if t in prices_wide.columns]
        
        n_tickers = len(valid_tickers)
        
        # Handle edge case: basket with <2 usable tickers
        if n_tickers < 2:
            results.append({
                "basket": basket_name,
                "n_tickers": n_tickers,
                "basket_vol": float('nan'),
                "opp_count": 0,
                "top_movers": "",
            })
            continue
        
        # Compute basket volatility over last analytics_window bars
        basket_vol_value = float('nan')
        try:
            basket_ret = basket_return(logret, valid_tickers)
            if len(basket_ret) >= settings.analytics_window:
                recent_basket_ret = basket_ret.tail(settings.analytics_window)
                basket_vol_value = float(recent_basket_ret.std()) if len(recent_basket_ret) > 1 else float('nan')
            elif len(basket_ret) > 1:
                # Use available data if less than analytics_window
                basket_vol_value = float(basket_ret.std())
        except Exception:
            basket_vol_value = float('nan')
        
        # Count opportunities: pairs where abs(z) >= z_entry AND boll_breach is True at latest
        opp_count = 0
        pairs = list(combinations(valid_tickers, 2))
        
        # Check if we have enough data for rolling windows
        has_enough_data = len(prices_wide) >= settings.z_window
        
        if has_enough_data:
            for a, b in pairs:
                try:
                    spread = spread_series(prices_wide, a, b)
                    zscore_series = zscore(spread, settings.z_window)
                    mid, upper_band, lower_band = bollinger_bands(spread, settings.z_window, settings.boll_k)
                    latest_breach = latest_boll_breach(spread, upper_band, lower_band)
                    
                    # Check latest z-score
                    if not zscore_series.empty and not pd.isna(zscore_series.iloc[-1]):
                        latest_z = float(zscore_series.iloc[-1])
                        if abs(latest_z) >= settings.z_entry and latest_breach:
                            opp_count += 1
                except Exception:
                    continue  # Skip pairs that fail
        
        # Top movers: top 3 tickers by abs return over lookback_bars
        top_movers = ""
        try:
            if len(logret) >= lookback_bars:
                recent_logret = logret[valid_tickers].tail(lookback_bars)
            else:
                recent_logret = logret[valid_tickers]
            
            if not recent_logret.empty and len(recent_logret) > 0:
                abs_returns = recent_logret.abs().sum()
                top_3 = abs_returns.nlargest(3)
                top_movers = ", ".join(top_3.index.tolist())
        except Exception:
            top_movers = ""
        
        results.append({
            "basket": basket_name,
            "n_tickers": n_tickers,
            "basket_vol": basket_vol_value,
            "opp_count": opp_count,
            "top_movers": top_movers,
        })
    
    # Create DataFrame and sort by basket_vol desc, then opp_count desc
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(["basket_vol", "opp_count"], ascending=[False, False], na_position="last")
    
    return df


def scan_pairs_in_basket(prices_wide: pd.DataFrame, basket_tickers: list[str], settings) -> pd.DataFrame:
    """Scan all pairs in a basket and return metrics.
    
    Args:
        prices_wide: DataFrame with datetime index and price columns
        basket_tickers: List of ticker symbols in the basket
        settings: Settings object with z_window, boll_k, analytics_window
        
    Returns:
        DataFrame with columns: a, b, z, boll_breach, bars_since_breach, corr, spread_vol
        Sorted by abs(z) descending
    """
    logret = log_returns(prices_wide)
    pairs = list(combinations(basket_tickers, 2))
    results = []
    
    for a, b in pairs:
        # Skip if tickers don't exist
        if a not in prices_wide.columns or b not in prices_wide.columns:
            continue
        
        try:
            # Compute spread and z-score
            spread = _compute_spread(prices_wide, a, b)
            zscore = _compute_zscore(spread, settings.z_window)
            latest_z = float(zscore.iloc[-1]) if not zscore.empty and not np.isnan(zscore.iloc[-1]) else np.nan
            
            # Compute Bollinger bands and breach
            upper_band, lower_band = _compute_bollinger_bands(spread, settings.z_window, settings.boll_k)
            breach = _detect_bollinger_breach(spread, upper_band, lower_band)
            latest_breach = bool(breach.iloc[-1]) if not breach.empty else False
            
            # Bars since breach
            bars_since = _compute_bars_since_breach(breach)
            
            # Correlation (latest 240-bar)
            corr_value = pair_corr_latest(logret, a, b, settings.analytics_window)
            
            # Spread volatility (latest 240-bar rolling std)
            rolling_std = spread.rolling(window=settings.analytics_window).std()
            spread_vol_value = float(rolling_std.iloc[-1]) if not rolling_std.empty and not np.isnan(rolling_std.iloc[-1]) else np.nan
            
            results.append({
                "a": a,
                "b": b,
                "z": latest_z,
                "boll_breach": latest_breach,
                "bars_since_breach": bars_since,
                "corr": corr_value,
                "spread_vol": spread_vol_value,
            })
        except Exception:
            continue  # Skip pairs that fail
    
    df = pd.DataFrame(results)
    
    # Sort by abs(z) descending, handling NaN values
    if not df.empty and "z" in df.columns:
        df["abs_z"] = df["z"].abs()
        df = df.sort_values("abs_z", ascending=False, na_last=True)
        df = df.drop(columns=["abs_z"])
    
    return df

