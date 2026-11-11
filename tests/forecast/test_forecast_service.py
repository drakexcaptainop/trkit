from datetime import date, datetime

import pandas as pd
import pytest

from briefkit.forecast.baseline import EwmaBaseline
from briefkit.forecast.horizons import HorizonForecast, ModelOutput
from briefkit.forecast.ledger import Ledger
from briefkit.forecast.service import ForecastService
from briefkit.marketdata.provider import Bar, ProviderError


class FakePrices:
    def __init__(self, closes, start=date(2026, 6, 1), error=None):
        self.error = error
        self.bars = []
        d = start
        for c in closes:
            while d.weekday() >= 5:
                d = date.fromordinal(d.toordinal() + 1)
            self.bars.append(Bar(date=d, open=c, high=c, low=c, close=c, volume=1))
            d = date.fromordinal(d.toordinal() + 1)

    def get_bars(self, ticker, lookback_days=730):
        if self.error:
            raise self.error
        return list(self.bars), []


class FixedModel:
    name = "fixed-model"

    def forecast(self, log_returns, horizons):
        return ModelOutput(
            model=self.name,
            forecasts=[HorizonForecast(h, 0.25, 0.25 * (h / 252) ** 0.5) for h in horizons],
        )


class BrokenModel:
    name = "broken-model"

    def forecast(self, log_returns, horizons):
        return ModelOutput(model=self.name, warnings=["could not be fitted"])


def wiggly(n=120):
    return [100.0 * (1.01 if i % 2 else 0.99) for i in range(n)]


def make(tmp_path, prices, models):
    ledger = Ledger(str(tmp_path / "l.sqlite"))
    svc = ForecastService(
        prices=prices,
        baseline=EwmaBaseline(),
        models=models,
        ledger=ledger,
        now=lambda: datetime(2026, 11, 20, 12, 0),
    )
    return svc, ledger


def test_forecast_writes_one_row_per_model_and_horizon_with_baseline_fields(tmp_path):
    svc, ledger = make(tmp_path, FakePrices(wiggly()), [FixedModel()])
    env = svc.forecast_volatility("NVDA")
    rows = ledger.rows()
    assert len(rows) == 3 * 2  # three horizons, fixed model plus the baseline itself
    fixed = [r for r in rows if r.model == "fixed-model"]
    assert {r.horizon for r in fixed} == {1, 5, 21}
    assert all(r.baseline_vol > 0 and r.ticker == "NVDA" for r in fixed)
    assert all(r.as_of == env.as_of for r in rows)


def test_every_model_forecast_is_returned_beside_the_baseline(tmp_path):
    svc, _ = make(tmp_path, FakePrices(wiggly()), [FixedModel()])
    data = svc.forecast_volatility("NVDA").data
    model = next(m for m in data["models"] if m["model"] == "fixed-model")
    for f in model["forecasts"]:
        assert set(f["baseline"]) == {"annualized_vol", "band_low", "band_high"}
        assert f["band_low"] < data["last_close"] < f["band_high"]


def test_repeating_the_call_does_not_duplicate_rows(tmp_path):
    svc, ledger = make(tmp_path, FakePrices(wiggly()), [FixedModel()])
    svc.forecast_volatility("NVDA")
    svc.forecast_volatility("NVDA")
    assert len(ledger.rows()) == 6


def test_a_model_that_cannot_fit_adds_a_warning_and_the_others_still_return(tmp_path):
    svc, ledger = make(tmp_path, FakePrices(wiggly()), [BrokenModel(), FixedModel()])
    env = svc.forecast_volatility("NVDA")
    assert any("broken-model" in w and "could not be fitted" in w for w in env.warnings)
    assert {m["model"] for m in env.data["models"]} == {"baseline-ewma", "fixed-model"}
    assert "broken-model" not in {r.model for r in ledger.rows()}


def test_scoring_an_elapsed_forecast_shows_actual_move_and_both_ranges(tmp_path):
    prices = FakePrices(wiggly(120))
    svc, _ledger = make(tmp_path, prices, [FixedModel()])
    # log a forecast as of six trading days before the end of the series
    earlier = FakePrices(wiggly(114))
    svc._prices = earlier
    svc.forecast_volatility("NVDA")
    svc._prices = prices
    result = svc.score_forecasts("NVDA")
    five = [
        s for s in result.data["forecasts"] if s["horizon"] == 5 and s["model"] == "fixed-model"
    ]
    assert five[0]["status"] == "scored"
    assert {"actual_return", "model_band", "baseline_band"} <= set(five[0])
    # the 21-day forecast has not elapsed yet
    pending = [s for s in result.data["forecasts"] if s["horizon"] == 21]
    assert all(s["status"] == "pending" for s in pending)


def test_a_data_failure_during_scoring_is_reported_and_the_ledger_is_untouched(tmp_path):
    svc, ledger = make(tmp_path, FakePrices(wiggly()), [FixedModel()])
    svc.forecast_volatility("NVDA")
    before = ledger.rows()
    svc._prices = FakePrices([], error=ProviderError("429 Too Many Requests"))
    result = svc.score_forecasts("NVDA")
    assert any("429" in w for w in result.warnings)
    assert result.data["forecasts"] == []
    assert ledger.rows() == before


def test_forecast_with_unusable_history_is_an_error(tmp_path):
    svc, _ = make(tmp_path, FakePrices([100.0, 101.0]), [FixedModel()])
    with pytest.raises(ValueError, match="history"):
        svc.forecast_volatility("NVDA")


def test_score_with_an_empty_ledger_says_so(tmp_path):
    svc, _ = make(tmp_path, FakePrices(wiggly()), [FixedModel()])
    result = svc.score_forecasts()
    assert result.data["forecasts"] == []
    assert pd.notna(result.as_of)
