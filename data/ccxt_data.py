"""Fetch OHLCV data from CCXT exchanges."""
import streamlit as st
import pandas as pd
import ccxt
import time


@st.cache_resource
def get_exchange(exchange_id: str):
    """Get CCXT exchange instance with rate limiting enabled.
    
    Args:
        exchange_id: Exchange identifier (e.g., 'binance')
        
    Returns:
        CCXT exchange instance
    """
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True})
    return exchange


def to_ccxt_symbol(raw: str) -> str:
    """Convert raw symbol string to CCXT format.
    
    Args:
        raw: Raw symbol string (e.g., 'ETHUSD', 'BCHBTC', 'ETH/USDT')
        
    Returns:
        CCXT-formatted symbol (e.g., 'ETH/USDT:USDT', 'BCH/BTC', 'ETH/USDT')
    """
    if raw is None:
        return raw
    s = raw.strip().upper()
    if "/" in s:
        return s  # already CCXT-like
    
    # handle BCHBTC style crosses
    if s.endswith("BTC") and len(s) > 3:
        base = s[:-3]
        return f"{base}/BTC"
    
    # treat *USD and *USDT as USDT-margined perp by default
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}/USDT:USDT"
    if s.endswith("USD"):
        base = s[:-3]
        return f"{base}/USDT:USDT"
    
    return s


def normalize_symbols(symbols: list[str]) -> list[str]:
    """Normalize list of symbols to CCXT format.
    
    Args:
        symbols: List of symbol strings (e.g., ['ETHUSD', 'BCHBTC'])
        
    Returns:
        List of CCXT-formatted symbols
    """
    return [to_ccxt_symbol(x) for x in symbols]


@st.cache_data
def fetch_ohlcv_close_wide(
    exchange_id: str,
    symbols: list[str],
    timeframe: str,
    days_fetch: int,
) -> pd.DataFrame:
    """Fetch OHLCV close prices for multiple symbols and return wide DataFrame.
    
    Args:
        exchange_id: Exchange identifier (e.g., 'binance')
        symbols: List of CCXT symbols (e.g., ['BTC/USDT', 'ETH/USDT'])
        timeframe: Timeframe string (e.g., '1h')
        days_fetch: Number of days of history to fetch
        
    Returns:
        DataFrame with datetime index and symbol columns (close prices)
        
    Raises:
        ValueError: If 0 symbols successfully fetched
        Exception: If other critical error occurs
    """
    exchange = get_exchange(exchange_id)
    
    # Load markets to validate symbols
    exchange.load_markets()
    
    # Convert and normalize symbols
    normalized_symbols = normalize_symbols(symbols)
    
    # Filter out symbols not present in exchange.markets
    valid_symbols = []
    missing_symbols = []
    for norm_sym in normalized_symbols:
        if norm_sym in exchange.markets:
            valid_symbols.append(norm_sym)
        else:
            missing_symbols.append(norm_sym)
    
    # If no valid symbols remain, raise ValueError
    if not valid_symbols:
        raise ValueError(f"No valid symbols found. Missing symbols: {missing_symbols}")
    
    # Parse timeframe to get milliseconds per candle
    timeframe_ms = exchange.parse_timeframe(timeframe) * 1000
    
    # Calculate since timestamp (milliseconds)
    now_ms = int(time.time() * 1000)
    since = now_ms - (days_fetch * 24 * 60 * 60 * 1000)
    
    # Collect close price Series for each symbol
    close_series_list = []
    errors = {}
    
    for symbol in valid_symbols:
        try:
            # Fetch OHLCV data
            ohlcv_data = exchange.fetch_ohlcv(
                symbol, timeframe=timeframe, since=since, limit=2000
            )
            
            if not ohlcv_data:
                errors[symbol] = "No data returned"
                continue
            
            # Build DataFrame
            df = pd.DataFrame(
                ohlcv_data,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            
            # Convert timestamp to pandas datetime (UTC), then make timezone-naive
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df["timestamp"] = df["timestamp"].dt.tz_localize(None)
            
            # Extract close prices as Series named by symbol
            close_series = df.set_index("timestamp")["close"]
            close_series.name = symbol
            close_series_list.append(close_series)
            
        except Exception as e:
            errors[symbol] = str(e)
            continue
    
    if not close_series_list:
        error_msg = f"Failed to fetch data for all symbols. Errors: {errors}"
        raise ValueError(error_msg)
    
    # Concatenate into wide DataFrame with aligned datetime index
    prices_wide = pd.concat(close_series_list, axis=1)
    prices_wide = prices_wide.sort_index()
    
    # Forward-fill within reason (only fill small gaps, not massive ones)
    # Use limit=3 to only fill gaps up to 3 periods
    prices_wide = prices_wide.ffill(limit=3)
    
    return prices_wide


def trim_history(prices_wide: pd.DataFrame, days_display: int) -> pd.DataFrame:
    """Trim prices_wide DataFrame to last N days.
    
    Args:
        prices_wide: DataFrame with datetime index and symbol columns
        days_display: Number of days to keep from the end
        
    Returns:
        Trimmed DataFrame
    """
    if prices_wide.empty:
        return prices_wide
    
    end_date = prices_wide.index.max()
    start_date = end_date - pd.Timedelta(days=days_display)
    trimmed = prices_wide[prices_wide.index >= start_date]
    return trimmed


def get_data_health(prices_wide: pd.DataFrame) -> dict:
    """Get data health metrics for a prices DataFrame.
    
    Args:
        prices_wide: DataFrame with datetime index and symbol columns
        
    Returns:
        Dict with keys: n_rows, n_cols, start_ts, end_ts, overall_missing_pct, per_symbol_missing_top10
    """
    if prices_wide.empty:
        return {
            "n_rows": 0,
            "n_cols": 0,
            "start_ts": None,
            "end_ts": None,
            "overall_missing_pct": 0.0,
            "per_symbol_missing_top10": [],
        }
    
    n_rows = len(prices_wide)
    n_cols = len(prices_wide.columns)
    start_ts = prices_wide.index.min()
    end_ts = prices_wide.index.max()
    
    # Overall missing percentage
    overall_missing_pct = (prices_wide.isna().sum().sum() / prices_wide.size) * 100
    
    # Per-symbol missing percentages
    per_symbol_missing = []
    for col in prices_wide.columns:
        missing_pct = (prices_wide[col].isna().sum() / n_rows) * 100
        per_symbol_missing.append((col, missing_pct))
    
    # Sort by missing_pct descending and take top 10
    per_symbol_missing.sort(key=lambda x: x[1], reverse=True)
    per_symbol_missing_top10 = per_symbol_missing[:10]
    
    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "overall_missing_pct": float(overall_missing_pct),
        "per_symbol_missing_top10": per_symbol_missing_top10,
    }

