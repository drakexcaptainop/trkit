"""Pretrained time-series forecaster (Chronos-2) applied to a rolling volatility series.

The model is optional: it needs the `foundation` extra (torch + chronos-forecasting) and a
one-time model download. When either is missing the forecaster reports a warning instead of
failing, so the rest of the brief still works.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd

from briefkit.forecast.horizons import TRADING_DAYS, HorizonForecast, ModelOutput

MIN_OBSERVATIONS = 250
ROLLING_WINDOW = 10  # days in each rolling realized-vol point
MODEL_ID = "amazon/chronos-2"


def rolling_vol(log_returns: pd.Series, window: int = ROLLING_WINDOW) -> np.ndarray:
    """Annualized root-mean-square of daily log returns over a rolling window."""
    squared = log_returns.pow(2).rolling(window).mean().dropna()
    return np.sqrt(squared.to_numpy() * TRADING_DAYS)


def _load_pipeline():
    from chronos import Chronos2Pipeline

    return Chronos2Pipeline.from_pretrained(MODEL_ID)


class ChronosForecaster:
    name = "chronos-2"

    def __init__(self, loader: Callable[[], object] = _load_pipeline):
        self._loader = loader
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            self._pipeline = self._loader()
        return self._pipeline

    def forecast(self, log_returns: pd.Series, horizons: Sequence[int]) -> ModelOutput:
        out = ModelOutput(model=self.name)
        if len(log_returns) < MIN_OBSERVATIONS:
            out.warnings.append(
                f"Not enough history for Chronos-2: {len(log_returns)} daily returns, "
                f"need at least {MIN_OBSERVATIONS}."
            )
            return out
        series = rolling_vol(log_returns)
        try:
            pipeline = self._get_pipeline()
            import torch

            quantiles, _ = pipeline.predict_quantiles(
                [torch.tensor(series, dtype=torch.float32)],
                prediction_length=max(horizons),
                quantile_levels=[0.5],
            )
            path = np.asarray(quantiles[0][0, :, 0], dtype=float)
        except ImportError as exc:
            out.warnings.append(
                f"Chronos-2 is not installed ({exc}); run `uv sync --extra foundation`."
            )
            return out
        except Exception as exc:  # noqa: BLE001 - a model failure must not break the brief
            out.warnings.append(f"Chronos-2 could not produce a forecast: {exc}")
            return out
        if not np.all(np.isfinite(path)) or np.any(path <= 0):
            out.warnings.append("Chronos-2 returned a non-positive or non-finite volatility path.")
            return out
        daily_variance = path**2 / TRADING_DAYS
        cumulative = np.cumsum(daily_variance)
        for h in horizons:
            total = float(cumulative[h - 1])
            out.forecasts.append(
                HorizonForecast(
                    horizon=h,
                    annualized_vol=math.sqrt(total / h * TRADING_DAYS),
                    horizon_sigma=math.sqrt(total),
                )
            )
        return out
