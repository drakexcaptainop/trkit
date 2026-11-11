"""Yahoo Finance daily bars through yfinance (unofficial; may throttle or break)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pandas as pd

from briefkit.marketdata.provider import Bar, InstrumentInfo, ProviderError


def _default_factory(ticker: str) -> Any:
    import yfinance

    return yfinance.Ticker(ticker)


class YahooProvider:
    name = "yahoo-finance (yfinance)"

    def __init__(self, ticker_factory: Callable[[str], Any] = _default_factory) -> None:
        self._factory = ticker_factory

    def get_instrument(self, ticker: str) -> InstrumentInfo:
        symbol = ticker.upper()
        try:
            info = self._factory(symbol).info or {}
        except Exception as exc:
            raise ProviderError(f"Yahoo lookup for {symbol} failed: {exc}") from exc
        quote_type = info.get("quoteType")
        if not quote_type:
            raise ProviderError(f"Ticker {symbol} not found on Yahoo Finance")
        return InstrumentInfo(
            ticker=symbol,
            quote_type=str(quote_type),
            exchange=str(info.get("exchange", "")),
            name=str(info.get("shortName") or info.get("longName") or symbol),
        )

    def get_daily_bars(self, ticker: str, start: date, end: date) -> list[Bar]:
        symbol = ticker.upper()
        try:
            frame = self._factory(symbol).history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=True,
            )
        except Exception as exc:
            raise ProviderError(f"Yahoo price download for {symbol} failed: {exc}") from exc
        if frame is None or frame.empty:
            return []
        frame = frame.dropna(subset=["Close"])
        index = pd.DatetimeIndex(frame.index)
        if index.tz is not None:
            index = index.tz_localize(None)
        out = []
        for ts, row in zip(index, frame.itertuples(index=False), strict=True):
            out.append(
                Bar(
                    date=ts.date(),
                    open=float(row.Open),
                    high=float(row.High),
                    low=float(row.Low),
                    close=float(row.Close),
                    volume=float(row.Volume),
                )
            )
        return out
