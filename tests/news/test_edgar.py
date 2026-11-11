from datetime import date

import pytest

from briefkit.news.edgar import EdgarClient
from briefkit.news.types import DiscoveryError

TICKERS = {"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"}}
SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["8-K", "4", "10-Q", "8-K"],
            "filingDate": ["2026-11-05", "2026-11-04", "2026-08-30", "2026-03-01"],
            "accessionNumber": [
                "0001045810-26-000100",
                "0001045810-26-000099",
                "0001045810-26-000080",
                "0001045810-26-000010",
            ],
            "primaryDocument": ["a8k.htm", "f4.xml", "q.htm", "old.htm"],
            "primaryDocDescription": ["Current report", "", "Quarterly report", ""],
        }
    }
}


def client():
    def get(url):
        return TICKERS if "company_tickers" in url else SUBMISSIONS

    return EdgarClient(get)


def test_recent_filings_keep_relevant_forms_inside_the_window():
    got = client().recent_filings("nvda", 60, date(2026, 11, 11))
    assert [(c.published, c.title) for c in got] == [
        ("2026-11-05", "NVDA Form 8-K - Current report"),
    ]
    assert got[0].url == (
        "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000100/a8k.htm"
    )
    assert got[0].kind == "filing"


def test_wider_window_includes_older_filings():
    got = client().recent_filings("NVDA", 90, date(2026, 11, 11))
    assert [c.published for c in got] == ["2026-11-05", "2026-08-30"]


def test_unknown_ticker_is_a_discovery_error():
    with pytest.raises(DiscoveryError, match="ZZZZ"):
        client().recent_filings("ZZZZ", 90, date(2026, 11, 11))
