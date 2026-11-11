import math

import pytest

from briefkit.forecast.horizons import HORIZONS, Z_10_90, band, log_returns


def test_horizon_set_is_one_five_and_twenty_one_days():
    assert HORIZONS == (1, 5, 21)


def test_log_returns_of_known_prices():
    r = log_returns([100.0, 110.0, 99.0])
    assert r.iloc[0] == pytest.approx(math.log(1.1))
    assert r.iloc[1] == pytest.approx(math.log(0.9))
    assert len(r) == 2


def test_band_is_symmetric_in_log_space_around_the_last_close():
    # hand computed: sigma 0.02, close 100 -> 100 * exp(+/- 1.2815515655 * 0.02)
    low, high = band(last_close=100.0, horizon_sigma=0.02)
    assert low == pytest.approx(100.0 * math.exp(-Z_10_90 * 0.02))
    assert high == pytest.approx(100.0 * math.exp(Z_10_90 * 0.02))
    assert low == pytest.approx(97.469, abs=0.01)
    assert high == pytest.approx(102.597, abs=0.01)


def test_zero_sigma_collapses_the_band_to_the_close():
    assert band(last_close=50.0, horizon_sigma=0.0) == (50.0, 50.0)
