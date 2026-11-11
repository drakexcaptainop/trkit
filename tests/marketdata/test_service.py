from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from briefkit.marketdata.provider import (
    Bar,
    InstrumentInfo,
    ProviderError,
    UnsupportedAssetError,
)
from briefkit.marketdata.service import PriceService

ET = ZoneInfo("America/New_York")


def after_close():
    return datetime(2026, 11, 11, 18, 0, tzinfo=ET)


def during_session():
    return datetime(2026, 11, 11, 11, 0, tzinfo=ET)


class FakeProvider:
    name = "fake"

    def __init__(self, info, bars):
        self._info = info
        self._bars = bars
        self.requested = []

    def get_instrument(self, ticker):
        return self._info

    def get_daily_bars(self, ticker, start, end):
        self.requested.append((ticker, start, end))
        return self._bars


def bars(*days):
    return [Bar(date=d, open=1.0, high=2.0, low=0.5, close=1.5, volume=100) for d in days]


EQUITY = InstrumentInfo(ticker="NVDA", quote_type="EQUITY", exchange="NMS", name="NVIDIA")
ETF = InstrumentInfo(ticker="SPY", quote_type="ETF", exchange="PCX", name="SPDR S&P 500")


def test_us_equity_returns_sorted_bars_and_as_of_is_last_bar():
    unsorted = bars(date(2026, 11, 10), date(2026, 11, 6), date(2026, 11, 9))
    svc = PriceService(FakeProvider(EQUITY, unsorted), now=after_close)
    env = svc.get_price_history("NVDA", lookback_days=5)
    dates = [b["date"] for b in env.data["bars"]]
    assert dates == ["2026-11-06", "2026-11-09", "2026-11-10"]
    assert env.as_of == "2026-11-10"
    assert env.source == "fake"


def test_etf_is_supported():
    svc = PriceService(FakeProvider(ETF, bars(date(2026, 11, 10))), now=after_close)
    assert svc.get_price_history("SPY", lookback_days=5).as_of == "2026-11-10"


@pytest.mark.parametrize(
    "info",
    [
        InstrumentInfo(
            ticker="BTC-USD", quote_type="CRYPTOCURRENCY", exchange="CCC", name="Bitcoin"
        ),
        InstrumentInfo(ticker="7203.T", quote_type="EQUITY", exchange="JPX", name="Toyota"),
        InstrumentInfo(ticker="EURUSD=X", quote_type="CURRENCY", exchange="CCY", name="EUR/USD"),
    ],
)
def test_non_us_or_non_equity_is_rejected_without_bars(info):
    provider = FakeProvider(info, bars(date(2026, 11, 10)))
    svc = PriceService(provider, now=after_close)
    with pytest.raises(UnsupportedAssetError, match="not supported"):
        svc.get_price_history(info.ticker, lookback_days=5)
    assert provider.requested == []


def test_short_history_adds_warning_with_actual_start_date():
    provider = FakeProvider(EQUITY, bars(date(2026, 10, 20), date(2026, 11, 10)))
    svc = PriceService(provider, now=after_close)
    env = svc.get_price_history("NVDA", lookback_days=365)
    assert any("2026-10-20" in w for w in env.warnings)


def test_full_history_has_no_warning():
    provider = FakeProvider(EQUITY, bars(date(2026, 11, 2), date(2026, 11, 10)))
    svc = PriceService(provider, now=after_close)
    env = svc.get_price_history("NVDA", lookback_days=10)
    assert env.warnings == []


def test_empty_provider_result_is_an_error():
    svc = PriceService(FakeProvider(EQUITY, []), now=after_close)
    with pytest.raises(ProviderError, match="no price data"):
        svc.get_price_history("NVDA", lookback_days=5)


def test_a_second_provider_changes_nothing_about_the_output_shape():
    a = PriceService(FakeProvider(EQUITY, bars(date(2026, 11, 10))), now=after_close)
    other = FakeProvider(EQUITY, bars(date(2026, 11, 10)))
    other.name = "another"
    b = PriceService(other, now=after_close)
    da = a.get_price_history("NVDA", lookback_days=5).to_dict()
    db = b.get_price_history("NVDA", lookback_days=5).to_dict()
    assert da.keys() == db.keys()
    assert da["data"] == db["data"]
    assert db["source"] == "another"


def test_todays_partial_bar_is_dropped_while_the_market_is_open():
    provider = FakeProvider(EQUITY, bars(date(2026, 11, 10), date(2026, 11, 11)))
    svc = PriceService(provider, now=during_session)
    env = svc.get_price_history("NVDA", lookback_days=5)
    assert env.as_of == "2026-11-10"
    assert [b["date"] for b in env.data["bars"]] == ["2026-11-10"]


def test_todays_bar_is_kept_after_the_close():
    provider = FakeProvider(EQUITY, bars(date(2026, 11, 10), date(2026, 11, 11)))
    svc = PriceService(provider, now=after_close)
    assert svc.get_price_history("NVDA", lookback_days=5).as_of == "2026-11-11"
