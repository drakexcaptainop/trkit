"""Pure scoring functions: compare a logged forecast with what the price actually did."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from briefkit.forecast.horizons import TRADING_DAYS
from briefkit.forecast.ledger import LedgerRow

BASELINE_MODEL = "baseline-ewma"


def realized_return(last_close: float, forward_closes: Sequence[float], horizon: int) -> float:
    return math.log(forward_closes[horizon - 1] / last_close)


def realized_vol(last_close: float, forward_closes: Sequence[float], horizon: int) -> float:
    closes = [last_close, *forward_closes[:horizon]]
    daily = [math.log(closes[i + 1] / closes[i]) for i in range(horizon)]
    return math.sqrt(sum(r * r for r in daily) / horizon * TRADING_DAYS)


@dataclass(frozen=True)
class ScoredForecast:
    ticker: str
    as_of: str
    horizon: int
    model: str
    status: str  # "scored" or "pending"
    forecast_vol: float
    baseline_vol: float
    model_band_low: float
    model_band_high: float
    baseline_band_low: float
    baseline_band_high: float
    actual_close: float | None = None
    actual_return: float | None = None
    actual_vol: float | None = None
    model_vol_error: float | None = None
    baseline_vol_error: float | None = None
    model_covered: bool | None = None
    baseline_covered: bool | None = None
    outcome: str | None = None  # "model", "baseline" or "tie"

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "as_of": self.as_of,
            "horizon": self.horizon,
            "model": self.model,
            "status": self.status,
            "forecast_vol": self.forecast_vol,
            "baseline_vol": self.baseline_vol,
            "model_band": [self.model_band_low, self.model_band_high],
            "baseline_band": [self.baseline_band_low, self.baseline_band_high],
            "actual_close": self.actual_close,
            "actual_return": self.actual_return,
            "actual_vol": self.actual_vol,
            "model_vol_error": self.model_vol_error,
            "baseline_vol_error": self.baseline_vol_error,
            "model_covered": self.model_covered,
            "baseline_covered": self.baseline_covered,
            "outcome": self.outcome,
        }


def score_forecast(row: LedgerRow, forward_closes: Sequence[float]) -> ScoredForecast:
    """Score one logged forecast. forward_closes are the closes after the as-of date, in order."""
    common = {
        "ticker": row.ticker,
        "as_of": row.as_of,
        "horizon": row.horizon,
        "model": row.model,
        "forecast_vol": row.annualized_vol,
        "baseline_vol": row.baseline_vol,
        "model_band_low": row.band_low,
        "model_band_high": row.band_high,
        "baseline_band_low": row.baseline_band_low,
        "baseline_band_high": row.baseline_band_high,
    }
    if len(forward_closes) < row.horizon:
        return ScoredForecast(status="pending", **common)
    actual_close = float(forward_closes[row.horizon - 1])
    actual_vol = realized_vol(row.last_close, forward_closes, row.horizon)
    model_error = abs(row.annualized_vol - actual_vol)
    baseline_error = abs(row.baseline_vol - actual_vol)
    if math.isclose(model_error, baseline_error, rel_tol=1e-9, abs_tol=1e-12):
        outcome = "tie"
    else:
        outcome = "model" if model_error < baseline_error else "baseline"
    return ScoredForecast(
        status="scored",
        actual_close=actual_close,
        actual_return=realized_return(row.last_close, forward_closes, row.horizon),
        actual_vol=actual_vol,
        model_vol_error=model_error,
        baseline_vol_error=baseline_error,
        model_covered=row.band_low <= actual_close <= row.band_high,
        baseline_covered=row.baseline_band_low <= actual_close <= row.baseline_band_high,
        outcome=outcome,
        **common,
    )


def summarize(scored: Sequence[ScoredForecast]) -> list[dict]:
    """Per model and horizon: how many forecasts were scored, and how they did."""
    groups: dict[tuple[str, int], list[ScoredForecast]] = defaultdict(list)
    for s in scored:
        groups[(s.model, s.horizon)].append(s)
    out = []
    for (model, horizon), items in sorted(groups.items()):
        done = [s for s in items if s.status == "scored"]
        entry = {
            "model": model,
            "horizon": horizon,
            "scored": len(done),
            "pending": len(items) - len(done),
            "mean_vol_error": (sum(s.model_vol_error for s in done) / len(done)) if done else None,
            "band_coverage": (sum(s.model_covered for s in done) / len(done)) if done else None,
        }
        if model != BASELINE_MODEL:
            entry["beat_baseline"] = sum(s.outcome == "model" for s in done)
            entry["lost_to_baseline"] = sum(s.outcome == "baseline" for s in done)
            entry["ties"] = sum(s.outcome == "tie" for s in done)
        out.append(entry)
    return out
