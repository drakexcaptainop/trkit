"""MCP server exposing volatility forecasts and their scoring."""

from __future__ import annotations

from fastmcp import FastMCP

from briefkit.common.config import Settings
from briefkit.forecast.baseline import EwmaBaseline
from briefkit.forecast.garch import GarchForecaster
from briefkit.forecast.ledger import Ledger
from briefkit.forecast.service import ForecastService
from briefkit.marketdata.service import PriceService
from briefkit.marketdata.yahoo import YahooProvider

mcp = FastMCP("briefkit-forecast")
_service: ForecastService | None = None


def _get_service() -> ForecastService:
    global _service
    if _service is None:
        settings = Settings.from_env()
        _service = ForecastService(
            prices=PriceService(YahooProvider()),
            baseline=EwmaBaseline(),
            models=[GarchForecaster()],
            ledger=Ledger(settings.ledger_path),
        )
    return _service


@mcp.tool
def forecast_volatility(ticker: str, lookback_days: int = 730) -> dict:
    """Volatility and expected price-range forecasts for a US stock or ETF.

    Fetches daily prices itself. Returns, for horizons of 1, 5 and 21 trading days, each
    model's annualized volatility and 10th-90th percentile price band, each shown beside
    the naive baseline for the same horizon. Every forecast is logged for later scoring.
    These are risk ranges, not predictions of direction.
    """
    return _get_service().forecast_volatility(ticker, lookback_days).to_dict()


@mcp.tool
def score_forecasts(ticker: str | None = None) -> dict:
    """Compare earlier logged forecasts with what the price actually did.

    For forecasts whose horizon has elapsed, shows the actual move, the model's range and the
    baseline's range side by side, plus per-model sample sizes. Pending forecasts are listed
    as pending.
    """
    return _get_service().score_forecasts(ticker).to_dict()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
