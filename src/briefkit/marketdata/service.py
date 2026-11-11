"""Price history for a US stock or ETF, wrapped in the shared envelope."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from briefkit.common.envelope import Envelope
from briefkit.marketdata.provider import (
    Bar,
    PriceProvider,
    ProviderError,
    UnsupportedAssetError,
)

SUPPORTED_QUOTE_TYPES = {"EQUITY", "ETF"}
US_EXCHANGES = {"NMS", "NGM", "NCM", "NYQ", "ASE", "PCX", "BTS", "NAS", "NYS", "BATS"}
_START_SLACK_DAYS = 7
_ET = ZoneInfo("America/New_York")
_SESSION_DONE = time(16, 30)


def _now_et() -> datetime:
    return datetime.now(_ET)


def bar_to_dict(bar: Bar) -> dict:
    d = asdict(bar)
    d["date"] = bar.date.isoformat()
    return d


class PriceService:
    def __init__(self, provider: PriceProvider, now: Callable[[], datetime] = _now_et) -> None:
        self._provider = provider
        self._now = now

    def get_bars(self, ticker: str, lookback_days: int = 730) -> tuple[list[Bar], list[str]]:
        symbol = ticker.strip().upper()
        info = self._provider.get_instrument(symbol)
        if info.quote_type not in SUPPORTED_QUOTE_TYPES or info.exchange not in US_EXCHANGES:
            raise UnsupportedAssetError(
                f"{symbol} is a {info.quote_type} on exchange {info.exchange or 'unknown'}; "
                "asset type not supported. Only US-listed stocks and ETFs are supported."
            )
        now = self._now()
        end = now.date()
        start = end - timedelta(days=lookback_days)
        bars = sorted(self._provider.get_daily_bars(symbol, start, end), key=lambda b: b.date)
        if now.time() < _SESSION_DONE:
            # today's bar is still forming, so it is not a close
            bars = [b for b in bars if b.date < end]
        if not bars:
            raise ProviderError(f"The price source returned no price data for {symbol}")
        warnings = []
        if bars[0].date > start + timedelta(days=_START_SLACK_DAYS):
            warnings.append(
                f"History starts {bars[0].date.isoformat()}, later than the requested "
                f"start {start.isoformat()}; returning what exists."
            )
        return bars, warnings

    def get_price_history(self, ticker: str, lookback_days: int = 730) -> Envelope:
        bars, warnings = self.get_bars(ticker, lookback_days)
        return Envelope(
            data={"ticker": ticker.strip().upper(), "bars": [bar_to_dict(b) for b in bars]},
            source=self._provider.name,
            as_of=bars[-1].date.isoformat(),
            warnings=warnings,
        )
