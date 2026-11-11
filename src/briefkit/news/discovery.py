"""Combine discovery sources into one deduplicated, newest-first candidate list."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from briefkit.news.types import Candidate, DiscoveryError

Source = Callable[[], list[Candidate]]


def discover(sources: dict[str, Source], limit: int = 30) -> tuple[list[Candidate], list[str]]:
    """Run each source; a failing source becomes a warning, never an exception."""
    found: dict[str, Candidate] = {}
    warnings: list[str] = []
    for name, run in sources.items():
        try:
            for c in run():
                found.setdefault(c.url, c)
        except DiscoveryError as exc:
            warnings.append(f"{name}: {exc}")
    ordered = sorted(found.values(), key=lambda c: c.published or "", reverse=True)
    return ordered[:limit], warnings


def build_sources(ticker: str, settings, get_json, rss_text, today: date) -> dict[str, Source]:
    """Wire the real sources. get_json fetches EDGAR JSON; rss_text(url) returns feed text."""
    from briefkit.news.edgar import EdgarClient
    from briefkit.news.rss import feed_url, parse_feed

    return {
        "SEC filings": lambda: EdgarClient(get_json).recent_filings(
            ticker, settings.filings_window_days, today
        ),
        "News feed": lambda: parse_feed(
            rss_text(feed_url(ticker)), settings.news_window_days, today
        ),
    }
