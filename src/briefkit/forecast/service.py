"""Serve forecasts (logging each one) and score them later against what actually happened."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime
from typing import Protocol

from briefkit.common.envelope import Envelope
from briefkit.forecast.horizons import (
    HORIZONS,
    Forecaster,
    ModelOutput,
    band,
    log_returns,
)
from briefkit.forecast.ledger import Ledger, LedgerRow
from briefkit.forecast.scoring import BASELINE_MODEL, score_forecast, summarize
from briefkit.marketdata.provider import Bar, ProviderError, UnsupportedAssetError

SOURCE = "briefkit forecast ledger"


class PriceSource(Protocol):
    def get_bars(self, ticker: str, lookback_days: int = 730) -> tuple[list[Bar], list[str]]: ...


class ForecastService:
    def __init__(
        self,
        prices: PriceSource,
        baseline: Forecaster,
        models: Sequence[Forecaster],
        ledger: Ledger,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._prices = prices
        self._baseline = baseline
        self._models = list(models)
        self._ledger = ledger
        self._now = now

    def forecast_volatility(self, ticker: str, lookback_days: int = 730) -> Envelope:
        symbol = ticker.strip().upper()
        bars, warnings = self._prices.get_bars(symbol, lookback_days)
        closes = [b.close for b in bars]
        returns = log_returns(closes)
        last_close = closes[-1]
        as_of = bars[-1].date.isoformat()

        base = self._baseline.forecast(returns, HORIZONS)
        if not base.forecasts:
            raise ValueError(
                "Not enough price history to forecast: " + "; ".join(base.warnings or ["no data"])
            )
        base_by_h = {f.horizon: f for f in base.forecasts}
        outputs: list[ModelOutput] = [base] + [m.forecast(returns, HORIZONS) for m in self._models]

        rows: list[LedgerRow] = []
        models_data = []
        created = self._now().isoformat(timespec="seconds")
        for out in outputs:
            warnings.extend(f"{out.model}: {w}" for w in out.warnings)
            if not out.forecasts:
                continue
            entries = []
            for f in out.forecasts:
                low, high = band(last_close, f.horizon_sigma)
                b = base_by_h[f.horizon]
                b_low, b_high = band(last_close, b.horizon_sigma)
                entries.append(
                    {
                        "horizon": f.horizon,
                        "annualized_vol": f.annualized_vol,
                        "band_low": low,
                        "band_high": high,
                        "baseline": {
                            "annualized_vol": b.annualized_vol,
                            "band_low": b_low,
                            "band_high": b_high,
                        },
                    }
                )
                rows.append(
                    LedgerRow(
                        ticker=symbol,
                        as_of=as_of,
                        horizon=f.horizon,
                        model=out.model,
                        last_close=last_close,
                        annualized_vol=f.annualized_vol,
                        horizon_sigma=f.horizon_sigma,
                        band_low=low,
                        band_high=high,
                        baseline_vol=b.annualized_vol,
                        baseline_sigma=b.horizon_sigma,
                        baseline_band_low=b_low,
                        baseline_band_high=b_high,
                        created_at=created,
                    )
                )
            models_data.append({"model": out.model, "forecasts": entries})
        self._ledger.record(rows)
        return Envelope(
            data={
                "ticker": symbol,
                "last_close": last_close,
                "as_of": as_of,
                "models": models_data,
            },
            source=SOURCE,
            as_of=as_of,
            warnings=warnings,
        )

    def score_forecasts(self, ticker: str | None = None) -> Envelope:
        today = self._now().date()
        rows = self._ledger.rows(ticker)
        warnings: list[str] = []
        scored = []
        for symbol in sorted({r.ticker for r in rows}):
            mine = [r for r in rows if r.ticker == symbol]
            oldest = min(date.fromisoformat(r.as_of) for r in mine)
            try:
                bars, _ = self._prices.get_bars(symbol, (today - oldest).days + 10)
            except (ProviderError, UnsupportedAssetError) as exc:
                warnings.append(f"{symbol}: could not fetch prices for scoring: {exc}")
                continue
            for r in mine:
                made = date.fromisoformat(r.as_of)
                forward = [b.close for b in bars if b.date > made]
                scored.append(score_forecast(r, forward))
        return Envelope(
            data={
                "forecasts": [s.to_dict() for s in scored if s.model != BASELINE_MODEL],
                "summary": summarize(scored),
            },
            source=SOURCE,
            as_of=today.isoformat(),
            warnings=warnings,
        )
