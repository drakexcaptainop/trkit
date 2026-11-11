"""The interface every price source implements, plus the shared value types and errors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


class ProviderError(Exception):
    """The price source failed or returned nothing usable."""


class UnsupportedAssetError(Exception):
    """The instrument is not a US-listed stock or ETF."""


@dataclass(frozen=True)
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class InstrumentInfo:
    ticker: str
    quote_type: str
    exchange: str
    name: str


class PriceProvider(Protocol):
    name: str

    def get_instrument(self, ticker: str) -> InstrumentInfo: ...

    def get_daily_bars(self, ticker: str, start: date, end: date) -> list[Bar]: ...
