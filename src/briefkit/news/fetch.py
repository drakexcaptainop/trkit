"""Page fetching behind a small interface: robots.txt, rate limits, text extraction."""

from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass
from typing import Protocol
from urllib import robotparser
from urllib.parse import urlsplit

from briefkit.news.types import DiscoveryError

PER_HOST_INTERVAL = 1.0
MAX_REDIRECTS = 5


def check_public_url(url: str) -> None:
    """Refuse non-http(s) URLs and hosts that resolve to private, loopback or link-local IPs."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError(f"refusing non-http(s) URL: {url}")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443)
    except OSError as exc:
        raise FetchError(f"could not resolve {parts.hostname}: {exc}") from exc
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise FetchError(f"refusing to fetch a non-public address: {parts.hostname}")


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
    def __init__(self, user_agent: str, text_cap: int = 12000, sec_user_agent: str | None = None):
        self._ua = user_agent
        self._sec_ua = sec_user_agent
        self._cap = text_cap
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self._last: dict[str, float] = {}

    def _agent_for(self, url: str) -> str:
        host = urlsplit(url).hostname or ""
        if self._sec_ua and (host == "sec.gov" or host.endswith(".sec.gov")):
            return self._sec_ua
        return self._ua

    def _allowed(self, url: str) -> bool:
        import httpx

        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            parser = robotparser.RobotFileParser()
            try:
                resp = httpx.get(
                    f"{host}/robots.txt",
                    headers={"User-Agent": self._agent_for(url)},
                    timeout=10,
                )
                parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
                self._robots[host] = parser
            except httpx.HTTPError:
                self._robots[host] = None
        parser = self._robots[host]
        return True if parser is None else parser.can_fetch(self._agent_for(url), url)

    def fetch(self, url: str) -> FetchedPage:
        import httpx
        import trafilatura

        html = ""
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            check_public_url(current)
            if not self._allowed(current):
                raise FetchError(f"robots.txt disallows fetching {current}")
            host = urlsplit(current).netloc
            wait = PER_HOST_INTERVAL - (time.monotonic() - self._last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.monotonic()
            try:
                resp = httpx.get(
                    current, headers={"User-Agent": self._agent_for(current)}, timeout=20
                )
            except (httpx.HTTPError, httpx.InvalidURL) as exc:
                raise FetchError(f"could not fetch {current}: {exc}") from exc
            if resp.is_redirect and resp.headers.get("location"):
                current = str(httpx.URL(current).join(resp.headers["location"]))
                continue
            if resp.status_code >= 400:
                raise FetchError(f"could not fetch {current}: HTTP {resp.status_code}")
            html = resp.text
            break
        else:
            raise FetchError(f"too many redirects fetching {url}")
        text = trafilatura.extract(html, include_comments=False) or ""
        if not text:
            raise FetchError(f"no readable text at {url}")
        meta = trafilatura.extract_metadata(html)
        return FetchedPage(
            url=url,
            title=getattr(meta, "title", None),
            text=text[: self._cap],
            published=getattr(meta, "date", None),
        )
