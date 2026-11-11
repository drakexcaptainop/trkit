"""Page fetching behind a small interface: robots.txt, rate limits, text extraction."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol
from urllib import robotparser
from urllib.parse import urlsplit

from briefkit.news.types import DiscoveryError

PER_HOST_INTERVAL = 1.0


@dataclass(frozen=True)
class FetchedPage:
    url: str
    title: str | None
    text: str
    published: str | None  # ISO date from page metadata, if the page declares one


class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchedPage: ...


class FetchError(DiscoveryError):
    """A page could not be fetched; the agent sees this as a tool error."""


class HttpFetcher:
    def __init__(self, user_agent: str, text_cap: int = 12000):
        self._ua = user_agent
        self._cap = text_cap
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self._last: dict[str, float] = {}

    def _allowed(self, url: str) -> bool:
        import httpx

        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            parser = robotparser.RobotFileParser()
            try:
                resp = httpx.get(
                    f"{host}/robots.txt",
                    headers={"User-Agent": self._ua},
                    timeout=10,
                    follow_redirects=True,
                )
                parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
                self._robots[host] = parser
            except httpx.HTTPError:
                self._robots[host] = None
        parser = self._robots[host]
        return True if parser is None else parser.can_fetch(self._ua, url)

    def fetch(self, url: str) -> FetchedPage:
        import httpx
        import trafilatura

        if not self._allowed(url):
            raise FetchError(f"robots.txt disallows fetching {url}")
        host = urlsplit(url).netloc
        wait = PER_HOST_INTERVAL - (time.monotonic() - self._last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.monotonic()
        try:
            resp = httpx.get(
                url, headers={"User-Agent": self._ua}, timeout=20, follow_redirects=True
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise FetchError(f"could not fetch {url}: {exc}") from exc
        text = trafilatura.extract(resp.text, include_comments=False) or ""
        if not text:
            raise FetchError(f"no readable text at {url}")
        meta = trafilatura.extract_metadata(resp.text)
        return FetchedPage(
            url=url,
            title=getattr(meta, "title", None),
            text=text[: self._cap],
            published=getattr(meta, "date", None),
        )
