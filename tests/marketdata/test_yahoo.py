from datetime import date

import pandas as pd
import pytest

from briefkit.marketdata.provider import ProviderError
from briefkit.marketdata.yahoo import YahooProvider


class FakeTicker:
    def __init__(self, history_df, info):
        self._df = history_df
        self.info = info
        self.history_args = None

    def history(self, **kwargs):
        self.history_args = kwargs
        return self._df


def make_history(index):
    return pd.DataFrame(
        {
            "Open": [10.0] * len(index),
            "High": [11.0] * len(index),
            "Low": [9.0] * len(index),
            "Close": [10.5] * len(index),
            "Volume": [1000] * len(index),
        },
        index=index,
    )


def test_timezone_aware_index_becomes_plain_dates():
    idx = pd.DatetimeIndex(
        ["2026-11-09 00:00:00-05:00", "2026-11-10 00:00:00-05:00"], tz="America/New_York"
    )
    ticker = FakeTicker(make_history(idx), {})
    provider = YahooProvider(ticker_factory=lambda t: ticker)
    out = provider.get_daily_bars("NVDA", date(2026, 11, 1), date(2026, 11, 11))
    assert [b.date for b in out] == [date(2026, 11, 9), date(2026, 11, 10)]
    assert out[0].close == 10.5
    assert out[0].volume == 1000


def test_empty_frame_returns_no_bars():
    ticker = FakeTicker(pd.DataFrame(), {})
    provider = YahooProvider(ticker_factory=lambda t: ticker)
    assert provider.get_daily_bars("NVDA", date(2026, 11, 1), date(2026, 11, 11)) == []


def test_rows_with_missing_close_are_dropped():
    idx = pd.DatetimeIndex(["2026-11-09", "2026-11-10"])
    df = make_history(idx)
    df.loc[idx[1], "Close"] = float("nan")
    provider = YahooProvider(ticker_factory=lambda t: FakeTicker(df, {}))
    out = provider.get_daily_bars("NVDA", date(2026, 11, 1), date(2026, 11, 11))
    assert [b.date for b in out] == [date(2026, 11, 9)]


def test_instrument_info_maps_yahoo_fields():
    info = {"quoteType": "ETF", "exchange": "PCX", "shortName": "SPDR S&P 500"}
    provider = YahooProvider(ticker_factory=lambda t: FakeTicker(pd.DataFrame(), info))
    got = provider.get_instrument("spy")
    assert (got.ticker, got.quote_type, got.exchange, got.name) == (
        "SPY",
        "ETF",
        "PCX",
        "SPDR S&P 500",
    )


def test_unknown_ticker_with_empty_info_is_a_provider_error():
    provider = YahooProvider(ticker_factory=lambda t: FakeTicker(pd.DataFrame(), {}))
    with pytest.raises(ProviderError, match="not found"):
        provider.get_instrument("ZZZZZZ")


def test_upstream_exception_is_wrapped_as_provider_error():
    def boom(t):
        raise RuntimeError("429 Too Many Requests")

    provider = YahooProvider(ticker_factory=boom)
    with pytest.raises(ProviderError, match="Too Many Requests"):
        provider.get_daily_bars("NVDA", date(2026, 11, 1), date(2026, 11, 11))
