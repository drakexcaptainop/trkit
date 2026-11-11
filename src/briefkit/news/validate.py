"""Code-side validation of what the local model reports. The model is never trusted for facts.

An item survives only if its URL is a discovered candidate, its page was fetched during this
run, and it has a date from the feed or the page's own metadata (never a model-written date).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta

from briefkit.news.fetch import FetchedPage
from briefkit.news.types import Candidate

SUMMARY_CAP = 600


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def validate(
    items: Sequence[object],
    candidates: Mapping[str, Candidate],
    fetched: Mapping[str, FetchedPage],
    *,
    today: date,
    news_window_days: int,
    filings_window_days: int,
) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        url = item["url"]
        if url in seen:
            continue
        cand = candidates.get(url)
        if cand is None:
            warnings.append(f"Dropped an item whose URL was not a discovered source: {url}")
            continue
        if url not in fetched:
            warnings.append(f"Dropped an item the agent never fetched: {url}")
            continue
        published = _parse_date(cand.published) or _parse_date(fetched[url].published)
        if published is None:
            warnings.append(f"Dropped an item with no verifiable date: {url}")
            continue
        window = filings_window_days if cand.kind == "filing" else news_window_days
        if published < today - timedelta(days=window):
            warnings.append(f"Dropped an item older than {window} days: {url}")
            continue
        seen.add(url)
        summary = item.get("summary")
        kept.append(
            {
                "title": cand.title,
                "url": url,
                "source": cand.source,
                "kind": cand.kind,
                "published": published.isoformat(),
                "summary": summary[:SUMMARY_CAP] if isinstance(summary, str) else "",
                "fetched": True,
            }
        )
    return kept, warnings
