"""Shared shapes for every forecaster: horizons, per-horizon results and the price band."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd

HORIZONS: tuple[int, ...] = (1, 5, 21)
TRADING_DAYS = 252
# 10th and 90th percentile of a standard normal
Z_10_90 = 1.2815515655446004


@dataclass(frozen=True)
class HorizonForecast:
    horizon: int
    annualized_vol: float
    horizon_sigma: float  # standard deviation of the log return over the horizon


@dataclass
class ModelOutput:
    model: str
    forecasts: list[HorizonForecast] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Forecaster(Protocol):
    name: str

    def forecast(self, log_returns: pd.Series, horizons: Sequence[int]) -> ModelOutput: ...


def log_returns(closes: Sequence[float]) -> pd.Series:
    arr = np.asarray(closes, dtype=float)
    return pd.Series(np.diff(np.log(arr)))


def band(last_close: float, horizon_sigma: float) -> tuple[float, float]:
    """10th to 90th percentile of the horizon return, as price levels from the last close."""
    return (
        last_close * math.exp(-Z_10_90 * horizon_sigma),
        last_close * math.exp(Z_10_90 * horizon_sigma),
    )
