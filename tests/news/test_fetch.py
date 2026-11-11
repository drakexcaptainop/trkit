import httpx
import pytest

from briefkit.news import fetch as fetch_mod
from briefkit.news.fetch import FetchError, HttpFetcher

HTML = (
    "<html><head><title>T</title><meta property='article:published_time' "
    "content='2026-11-03'></head><body><article><p>"
    + "Nvidia reported results. " * 40
    + "</p></article></body></html>"
)


class Resp:
    def __init__(self, status=200, text="", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}

    @property
    def is_redirect(self):
        return self.status_code in (301, 302) and "location" in self.headers


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    def fake(host, port):
        ip = "127.0.0.1" if host == "localhost" else "93.184.216.34"
        return [(0, 0, 0, "", (ip, port))]

    monkeypatch.setattr(fetch_mod.socket, "getaddrinfo", fake)
    monkeypatch.setattr(fetch_mod.time, "sleep", lambda s: None)


def install(monkeypatch, routes):
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append((url, headers["User-Agent"]))
        for suffix, resp in routes.items():
            if url.endswith(suffix):
                return resp() if callable(resp) else resp
        return Resp(404)

    monkeypatch.setattr(httpx, "get", get)
    return calls


def test_page_text_and_metadata_date_are_returned_and_capped(monkeypatch):
    install(monkeypatch, {"/robots.txt": Resp(200, ""), "/a": Resp(200, HTML)})
    page = HttpFetcher("ua", text_cap=100).fetch("https://example.com/a")
    assert page.published == "2026-11-03" and len(page.text) <= 100


def test_robots_disallow_is_refused(monkeypatch):
    install(
        monkeypatch, {"/robots.txt": Resp(200, "User-agent: *\nDisallow: /"), "/a": Resp(200, HTML)}
    )
    with pytest.raises(FetchError, match="robots"):
        HttpFetcher("ua").fetch("https://example.com/a")


def test_unreachable_robots_allows_the_fetch(monkeypatch):
    def boom():
        raise httpx.ConnectError("down")

    install(monkeypatch, {"/robots.txt": boom, "/a": Resp(200, HTML)})
    assert HttpFetcher("ua").fetch("https://example.com/a").text


def test_unreadable_page_is_a_fetch_error(monkeypatch):
    install(monkeypatch, {"/robots.txt": Resp(404), "/a": Resp(200, "<html></html>")})
    with pytest.raises(FetchError, match="no readable text"):
        HttpFetcher("ua").fetch("https://example.com/a")


def test_http_error_status_is_a_fetch_error(monkeypatch):
    install(monkeypatch, {"/robots.txt": Resp(404), "/a": Resp(403)})
    with pytest.raises(FetchError, match="403"):
        HttpFetcher("ua").fetch("https://example.com/a")


def test_private_and_non_http_urls_are_refused(monkeypatch):
    calls = install(monkeypatch, {})
    for url in ("http://localhost/admin", "file:///etc/passwd", "ftp://example.com/x"):
        with pytest.raises(FetchError):
            HttpFetcher("ua").fetch(url)
    assert calls == []


def test_redirect_to_a_private_host_is_refused(monkeypatch):
    install(
        monkeypatch,
        {
            "/robots.txt": Resp(404),
            "/a": Resp(302, headers={"location": "http://localhost/secret"}),
        },
    )
    with pytest.raises(FetchError, match="non-public"):
        HttpFetcher("ua").fetch("https://example.com/a")


def test_redirect_loop_is_bounded(monkeypatch):
    install(monkeypatch, {"/robots.txt": Resp(404), "/a": Resp(302, headers={"location": "/a"})})
    with pytest.raises(FetchError, match="too many redirects"):
        HttpFetcher("ua").fetch("https://example.com/a")


def test_sec_hosts_use_the_sec_contact_agent_and_others_do_not(monkeypatch):
    calls = install(monkeypatch, {"/robots.txt": Resp(404), "/doc.htm": Resp(200, HTML)})
    fetcher = HttpFetcher("generic", sec_user_agent="Me me@example.org")
    fetcher.fetch("https://www.sec.gov/Archives/doc.htm")
    fetcher.fetch("https://example.com/doc.htm")
    agents = {url: ua for url, ua in calls}
    assert agents["https://www.sec.gov/Archives/doc.htm"] == "Me me@example.org"
    assert agents["https://example.com/doc.htm"] == "generic"
