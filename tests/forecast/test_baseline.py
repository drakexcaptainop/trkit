import math

import pandas as pd
import pytest

from briefkit.forecast.baseline import EwmaBaseline
from briefkit.forecast.horizons import HORIZONS, band


def alternating(n, size=0.01):
    return pd.Series([size if i % 2 == 0 else -size for i in range(n)])


def test_flat_prices_give_zero_volatility_and_a_collapsed_band():
    out = EwmaBaseline().forecast(pd.Series([0.0] * 60), HORIZONS)
    assert out.warnings == []
    for f in out.forecasts:
        assert f.annualized_vol == 0.0
        assert band(100.0, f.horizon_sigma) == (100.0, 100.0)


def test_known_daily_size_gives_known_annualized_volatility():
    # every squared return is 0.0001, so the weighted average is exactly 0.0001
    out = EwmaBaseline().forecast(alternating(120), HORIZONS)
    one_day = out.forecasts[0]
    assert one_day.horizon == 1
    assert one_day.horizon_sigma == pytest.approx(0.01)
    assert one_day.annualized_vol == pytest.approx(0.01 * math.sqrt(252))


def test_horizon_sigma_grows_with_the_square_root_of_the_horizon():
    out = EwmaBaseline().forecast(alternating(120), HORIZONS)
    sig = {f.horizon: f.horizon_sigma for f in out.forecasts}
    assert sig[5] == pytest.approx(0.01 * math.sqrt(5))
    assert sig[21] == pytest.approx(0.01 * math.sqrt(21))
    low5, high5 = band(100.0, sig[5])
    low21, high21 = band(100.0, sig[21])
    assert (high21 - low21) > (high5 - low5)


def test_too_little_history_is_a_warning_not_an_exception():
    out = EwmaBaseline().forecast(alternating(5), HORIZONS)
    assert out.forecasts == []
    assert any("history" in w.lower() for w in out.warnings)


def test_recent_shock_raises_the_forecast_more_than_an_old_one():
    calm = [0.001, -0.001] * 40
    old_shock = pd.Series([0.05] + calm)
    new_shock = pd.Series(calm + [0.05])
    old = EwmaBaseline().forecast(old_shock, (1,)).forecasts[0].annualized_vol
    new = EwmaBaseline().forecast(new_shock, (1,)).forecasts[0].annualized_vol
    assert new > old
