"""Statistical arbitrage metrics calculations."""
import pandas as pd
import numpy as np


def log_returns(prices_wide: pd.DataFrame) -> pd.DataFrame:
    """Compute log returns from prices.
    
    Args:
        prices_wide: DataFrame with datetime index and price columns
        
    Returns:
        DataFrame with log returns (same index and columns)
    """
    return np.log(prices_wide / prices_wide.shift(1))


def rolling_vol(logret: pd.DataFrame, window: int) -> pd.DataFrame:
    """Compute rolling volatility (standard deviation) for each column.
    
    Args:
        logret: DataFrame with log returns
        window: Rolling window size
        
    Returns:
        DataFrame with rolling volatility per column
    """
    return logret.rolling(window=window).std()


def basket_return(logret: pd.DataFrame, tickers: list[str]) -> pd.Series:
    """Compute equal-weight basket return (mean of member log returns per bar).
    
    Args:
        logret: DataFrame with log returns
        tickers: List of column names to include in basket
        
    Returns:
        Series with basket log returns (datetime index)
        
    Raises:
        ValueError: If any ticker column is missing from logret
    """
    missing = [t for t in tickers if t not in logret.columns]
    if missing:
        raise ValueError(f"Missing columns in logret: {missing}")
    
    return logret[tickers].mean(axis=1)


def basket_vol(basket_ret: pd.Series) -> float:
    """Compute basket volatility (standard deviation over the series).
    
    Args:
        basket_ret: Series with basket returns
        
    Returns:
        Standard deviation as float
    """
    return float(basket_ret.std())


def rolling_corr(logret: pd.DataFrame, a: str, b: str, window: int) -> pd.Series:
    """Compute rolling correlation between two series.
    
    Args:
        logret: DataFrame with log returns
        a: First column name
        b: Second column name
        window: Rolling window size
        
    Returns:
        Series with rolling correlation (datetime index)
        
    Raises:
        ValueError: If column a or b is missing from logret
    """
    missing = [col for col in [a, b] if col not in logret.columns]
    if missing:
        raise ValueError(f"Missing columns in logret: {missing}")
    
    return logret[a].rolling(window=window).corr(logret[b])


def pair_corr_latest(logret: pd.DataFrame, a: str, b: str, window: int) -> float:
    """Get latest rolling correlation value between two series.
    
    Args:
        logret: DataFrame with log returns
        a: First column name
        b: Second column name
        window: Rolling window size
        
    Returns:
        Latest correlation value as float
        
    Raises:
        ValueError: If column a or b is missing from logret
    """
    rolling_corr_series = rolling_corr(logret, a, b, window)
    return float(rolling_corr_series.iloc[-1])

