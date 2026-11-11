"""GARCH(1,1) volatility forecaster built on the arch package."""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence

import numpy as np
import pandas as pd

from briefkit.forecast.horizons import TRADING_DAYS, HorizonForecast, ModelOutput

MIN_OBSERVATIONS = 250
_SCALE = 100.0  # arch is better conditioned on percent returns


class GarchForecaster:
    name = "garch-1-1"

    def forecast(self, log_returns: pd.Series, horizons: Sequence[int]) -> ModelOutput:
        out = ModelOutput(model=self.name)
        if len(log_returns) < MIN_OBSERVATIONS:
            out.warnings.append(
                f"Not enough history for GARCH: {len(log_returns)} daily returns, "
                f"need at least {MIN_OBSERVATIONS}."
            )
            return out
        try:
            from arch import arch_model

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = arch_model(
                    log_returns.to_numpy() * _SCALE, mean="Constant", vol="GARCH", p=1, q=1
                ).fit(disp="off")
                path = result.forecast(horizon=max(horizons), reindex=False).variance.to_numpy()[-1]
            if result.convergence_flag != 0:
                raise ValueError("the optimizer did not converge")
            cumulative = np.cumsum(path) / _SCALE**2
            if not np.all(np.isfinite(cumulative)) or cumulative[0] <= 0:
                raise ValueError("the fit produced a degenerate variance")
        except (ValueError, RuntimeError, ArithmeticError, np.linalg.LinAlgError) as exc:
            out.warnings.append(f"GARCH could not be fitted: {exc}")
            return out
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
