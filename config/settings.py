from dataclasses import dataclass


@dataclass
class Settings:
    exchange_id: str = "binance"
    timeframe: str = "1h"
    history_days_display: int = 10
    history_days_fetch: int = 12  # buffer for rolling windows
    z_window: int = 120
    analytics_window: int = 240
    boll_k: float = 2.0
    z_entry: float = 2.0
    cache_ttl_seconds: int = 300


def get_settings() -> Settings:
    """Return Settings instance with default values."""
    return Settings()

