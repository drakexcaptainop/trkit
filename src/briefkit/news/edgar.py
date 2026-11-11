"""SEC EDGAR discovery: recent filings for a ticker via the official JSON endpoints."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, timedelta

from briefkit.news.types import Candidate, DiscoveryError

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
FORMS = {"8-K", "10-K", "10-Q", "6-K", "20-F", "40-F", "S-1", "DEF 14A"}
MIN_INTERVAL = 0.125  # SEC allows 10 requests per second; stay at 8

GetJson = Callable[[str], dict]


def make_http_get_json(user_agent: str) -> GetJson:
    import httpx

    last = [0.0]

    def get(url: str) -> dict:
        wait = MIN_INTERVAL - (time.monotonic() - last[0])
        if wait > 0:
            time.sleep(wait)
        last[0] = time.monotonic()
        try:
            resp = httpx.get(
                url, headers={"User-Agent": user_agent}, timeout=20, follow_redirects=True
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DiscoveryError(f"SEC EDGAR request failed: {exc}") from exc

    return get


class EdgarClient:
    def __init__(self, get_json: GetJson):
        self._get = get_json

    def resolve_cik(self, ticker: str) -> int:
        wanted = ticker.upper()
        for entry in self._get(TICKERS_URL).values():
            if str(entry.get("ticker", "")).upper() == wanted:
                return int(entry["cik_str"])
        raise DiscoveryError(f"No SEC registrant found for ticker {wanted}.")

    def recent_filings(self, ticker: str, window_days: int, today: date) -> list[Candidate]:
        cik = self.resolve_cik(ticker)
        recent = self._get(SUBMISSIONS_URL.format(cik=cik)).get("filings", {}).get("recent", {})
        cutoff = (today - timedelta(days=window_days)).isoformat()
        out: list[Candidate] = []
        columns = zip(
            recent.get("form", []),
            recent.get("filingDate", []),
            recent.get("accessionNumber", []),
            recent.get("primaryDocument", []),
            recent.get("primaryDocDescription", []),
            strict=False,
        )
        for form, filed, acc, doc, desc in columns:
            if form not in FORMS or filed < cutoff or not doc:
                continue
            url = ARCHIVE_URL.format(cik=cik, acc=acc.replace("-", ""), doc=doc)
            out.append(
                Candidate(
                    url=url,
                    title=f"{ticker.upper()} Form {form}" + (f" - {desc}" if desc else ""),
                    kind="filing",
                    source="sec-edgar",
                    published=filed,
                )
            )
        return out
