import math

import numpy as np
import pandas as pd
import pytest

from briefkit.forecast.foundation import ChronosForecaster, rolling_vol


class FakePipeline:
    def __init__(self, path):
        self.path = path
        self.seen = None

    def predict_quantiles(self, inputs, prediction_length, quantile_levels):
        import torch

        self.seen = (inputs, prediction_length, quantile_levels)
        arr = torch.tensor(self.path[:prediction_length], dtype=torch.float32)
        return [arr.reshape(1, -1, 1)], [arr.reshape(1, -1)]


def returns(n=300, seed=0):
    return pd.Series(np.random.default_rng(seed).normal(0, 0.01, n))


def test_rolling_vol_is_annualized_rms_of_the_window():
    r = pd.Series([0.01] * 12)
    assert rolling_vol(r, window=10) == pytest.approx([0.01 * math.sqrt(252)] * 3)


def test_constant_vol_path_gives_matching_horizon_forecasts():
    pipe = FakePipeline([0.25] * 21)
    out = ChronosForecaster(loader=lambda: pipe).forecast(returns(), (1, 5, 21))
    assert out.warnings == []
    by_h = {f.horizon: f for f in out.forecasts}
    assert by_h[5].annualized_vol == pytest.approx(0.25)
    assert by_h[21].horizon_sigma == pytest.approx(0.25 * math.sqrt(21 / 252))
    assert pipe.seen[1] == 21


def test_short_history_warns_without_loading_the_model():
    def boom():
        raise AssertionError("model must not load")

    out = ChronosForecaster(loader=boom).forecast(returns(100), (1, 5, 21))
    assert out.forecasts == []
    assert "Not enough history" in out.warnings[0]


def test_missing_dependency_becomes_a_warning():
    def missing():
        raise ImportError("No module named 'chronos'")

    out = ChronosForecaster(loader=missing).forecast(returns(), (1, 5, 21))
    assert out.forecasts == []
    assert "uv sync --extra foundation" in out.warnings[0]


def test_model_failure_becomes_a_warning():
    def broken():
        raise OSError("download failed")

    out = ChronosForecaster(loader=broken).forecast(returns(), (1,))
    assert out.forecasts == []
    assert "download failed" in out.warnings[0]


def test_degenerate_path_is_rejected():
    out = ChronosForecaster(loader=lambda: FakePipeline([0.2, -0.1] + [0.2] * 19)).forecast(
        returns(), (1, 5, 21)
    )
    assert out.forecasts == []
    assert out.warnings
