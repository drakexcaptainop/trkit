import numpy as np
import pandas as pd

from briefkit.forecast.baseline import EwmaBaseline
from briefkit.forecast.garch import GarchForecaster
from briefkit.forecast.horizons import HORIZONS


def simulate_garch(n=1500, omega=2e-6, alpha=0.08, beta=0.90, seed=7):
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    var = omega / (1 - alpha - beta)
    for t in range(n):
        r[t] = np.sqrt(var) * rng.standard_normal()
        var = omega + alpha * r[t] ** 2 + beta * var
    return pd.Series(r)


def test_garch_returns_positive_forecasts_near_the_true_volatility():
    returns = simulate_garch()
    out = GarchForecaster().forecast(returns, HORIZONS)
    assert out.warnings == []
    assert [f.horizon for f in out.forecasts] == list(HORIZONS)
    true_annual = np.sqrt(2e-6 / (1 - 0.08 - 0.90) * 252)
    for f in out.forecasts:
        assert f.annualized_vol > 0
        assert 0.5 * true_annual < f.annualized_vol < 2.0 * true_annual


def test_garch_horizon_sigma_is_wider_for_longer_horizons():
    out = GarchForecaster().forecast(simulate_garch(), HORIZONS)
    sig = [f.horizon_sigma for f in out.forecasts]
    assert sig == sorted(sig)
    assert sig[0] < sig[-1]


def test_garch_with_too_little_history_warns_instead_of_raising():
    out = GarchForecaster().forecast(simulate_garch(n=40), HORIZONS)
    assert out.forecasts == []
    assert any("history" in w.lower() for w in out.warnings)


def test_garch_that_cannot_be_fitted_warns_and_returns_no_forecast():
    out = GarchForecaster().forecast(pd.Series([0.0] * 400), HORIZONS)
    assert out.forecasts == []
    assert out.warnings


def test_garch_and_baseline_return_the_same_fields():
    returns = simulate_garch()
    g = GarchForecaster().forecast(returns, HORIZONS).forecasts[0]
    b = EwmaBaseline().forecast(returns, HORIZONS).forecasts[0]
    assert g.__dataclass_fields__.keys() == b.__dataclass_fields__.keys()
    assert GarchForecaster.name != EwmaBaseline.name
