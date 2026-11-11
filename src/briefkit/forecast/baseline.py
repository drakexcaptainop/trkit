"""Naive baseline: exponentially weighted historical volatility held flat over the horizon."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pandas as pd

from briefkit.forecast.horizons import TRADING_DAYS, HorizonForecast, ModelOutput

MIN_OBSERVATIONS = 30
DECAY = 0.94
_SEED_WINDOW = 20


class EwmaBaseline:
    name = "baseline-ewma"

    def forecast(self, log_returns: pd.Series, horizons: Sequence[int]) -> ModelOutput:
        out = ModelOutput(model=self.name)
        if len(log_returns) < MIN_OBSERVATIONS:
            out.warnings.append(
                f"Not enough history for the baseline: {len(log_returns)} daily returns, "
                f"need at least {MIN_OBSERVATIONS}."
            )
            return out
        squares = [float(r) ** 2 for r in log_returns]
        variance = sum(squares[:_SEED_WINDOW]) / min(_SEED_WINDOW, len(squares))
        for sq in squares:
            variance = DECAY * variance + (1 - DECAY) * sq
        for h in horizons:
            out.forecasts.append(
                HorizonForecast(
                    horizon=h,
                    annualized_vol=math.sqrt(variance * TRADING_DAYS),
                    horizon_sigma=math.sqrt(variance * h),
                )
            )
        return out
