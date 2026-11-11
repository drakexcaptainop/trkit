"""MCP server exposing daily price history."""

from __future__ import annotations

from fastmcp import FastMCP

from briefkit.marketdata.service import PriceService
from briefkit.marketdata.yahoo import YahooProvider

mcp = FastMCP("briefkit-marketdata")
_service = PriceService(YahooProvider())


@mcp.tool
def get_price_history(ticker: str, lookback_days: int = 730) -> dict:
    """Daily price history (open, high, low, close, volume) for a US-listed stock or ETF.

    Returns the bars plus the data source and the date of the latest close (as_of).
    Fails with a clear message for crypto, foreign listings and other asset types.
    """
    return _service.get_price_history(ticker, lookback_days).to_dict()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
