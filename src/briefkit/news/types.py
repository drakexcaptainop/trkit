"""Shared shapes for news discovery."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    url: str
    title: str
    kind: str  # "filing" or "news"
    source: str  # e.g. "sec-edgar" or "yahoo-finance-rss"
    published: str | None  # ISO date (YYYY-MM-DD) taken from the feed, never model-written
    snippet: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "kind": self.kind,
            "source": self.source,
            "published": self.published,
            "snippet": self.snippet,
        }


class DiscoveryError(Exception):
    """A discovery source failed; the caller turns this into a warning."""
