import math

import pytest

from briefkit.forecast.ledger import LedgerRow
from briefkit.forecast.scoring import (
    realized_return,
    realized_vol,
    score_forecast,
    summarize,
)


def row(**over):
    base = {
        "ticker": "NVDA",
        "as_of": "2026-11-02",
        "horizon": 5,
        "model": "garch-1-1",
        "last_close": 100.0,
        "annualized_vol": 0.30,
        "horizon_sigma": 0.30 * math.sqrt(5 / 252),
        "band_low": 95.0,
        "band_high": 105.0,
        "baseline_vol": 0.20,
        "baseline_sigma": 0.20 * math.sqrt(5 / 252),
        "baseline_band_low": 97.0,
        "baseline_band_high": 103.0,
        "created_at": "2026-11-02T20:00:00",
    }
    base.update(over)
    return LedgerRow(**base)


FORWARD = [101.0, 102.0, 101.0, 103.0, 104.0, 105.0]  # six closes after the as-of date


def test_realized_return_is_the_log_move_to_the_horizon_close():
    assert realized_return(100.0, FORWARD, 5) == pytest.approx(math.log(104 / 100))


def test_realized_vol_is_annualized_root_mean_square_of_daily_log_returns():
    closes = [100.0] + FORWARD[:5]
    daily = [math.log(closes[i + 1] / closes[i]) for i in range(5)]
    expected = math.sqrt(sum(r * r for r in daily) / 5 * 252)
    assert realized_vol(100.0, FORWARD, 5) == pytest.approx(expected)


def test_one_day_realized_vol_is_the_absolute_daily_move_annualized():
    assert realized_vol(100.0, [101.0], 1) == pytest.approx(abs(math.log(1.01)) * math.sqrt(252))


def test_elapsed_forecast_shows_move_and_both_bands_side_by_side():
    s = score_forecast(row(), FORWARD)
    assert s.status == "scored"
    assert s.actual_close == 104.0
    assert s.actual_return == pytest.approx(math.log(1.04))
    assert (s.model_band_low, s.model_band_high) == (95.0, 105.0)
    assert (s.baseline_band_low, s.baseline_band_high) == (97.0, 103.0)
    assert s.model_covered is True
    assert s.baseline_covered is False


def test_pending_forecast_is_not_scored():
    s = score_forecast(row(), FORWARD[:4])
    assert s.status == "pending"
    assert s.actual_return is None
    assert s.model_covered is None


def test_return_exactly_on_the_band_edge_counts_as_covered():
    s = score_forecast(row(band_high=104.0), FORWARD)
    assert s.model_covered is True


def test_lower_vol_error_beats_the_baseline():
    realized = realized_vol(100.0, FORWARD, 5)
    close_model = row(annualized_vol=realized + 0.01, baseline_vol=realized + 0.20)
    s = score_forecast(close_model, FORWARD)
    assert s.outcome == "model"
    far_model = row(annualized_vol=realized + 0.30, baseline_vol=realized + 0.05)
    assert score_forecast(far_model, FORWARD).outcome == "baseline"


def test_equal_errors_are_reported_as_a_tie():
    realized = realized_vol(100.0, FORWARD, 5)
    s = score_forecast(row(annualized_vol=realized + 0.1, baseline_vol=realized - 0.1), FORWARD)
    assert s.outcome == "tie"


def test_summary_reports_sample_size_per_model_and_horizon():
    scored = [
        score_forecast(row(), FORWARD),
        score_forecast(row(as_of="2026-11-03"), FORWARD),
        score_forecast(row(horizon=1), FORWARD),
        score_forecast(row(as_of="2026-11-04"), FORWARD[:2]),  # pending
    ]
    summary = {(m["model"], m["horizon"]): m for m in summarize(scored)}
    assert summary[("garch-1-1", 5)]["scored"] == 2
    assert summary[("garch-1-1", 1)]["scored"] == 1
    assert summary[("garch-1-1", 5)]["pending"] == 1
