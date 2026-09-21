"""Тесты сетевого слоя: rate limiter, robots.txt, HTTP-клиент."""

from __future__ import annotations

import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar.net.client import HttpClient, HttpError, RobotsDisallowed  # noqa: E402
from medax_radar.net.ratelimit import HostRateLimiter, RateLimiter  # noqa: E402
from medax_radar.net.robots import RobotsCache  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class TestRateLimiter(unittest.TestCase):
    def test_burst_then_wait(self) -> None:
        clock = FakeClock()
        waited: list[float] = []
        limiter = RateLimiter(rate_per_sec=1.0, burst=1.0,
                              clock=clock, sleep=waited.append)
        self.assertEqual(limiter.acquire(), 0.0)   # токен из запаса
        self.assertEqual(limiter.acquire(), 1.0)   # ждём 1 сек
        self.assertEqual(waited, [1.0])

    def test_invalid_rate(self) -> None:
        with self.assertRaises(ValueError):
            RateLimiter(rate_per_sec=0)

    def test_host_isolation(self) -> None:
        clock = FakeClock()
        limiter = HostRateLimiter(rate_per_sec=1.0, burst=1.0,
                                  clock=clock, sleep=lambda _s: None)
        self.assertIsNot(limiter.limiter_for("https://a.test/x"),
                         limiter.limiter_for("https://b.test/y"))


class TestRobots(unittest.TestCase):
    def test_disallowed(self) -> None:
        text = "User-agent: *\nDisallow: /private"
        cache = RobotsCache(fetcher=lambda _u: text, user_agent="Bot")
        self.assertFalse(cache.can_fetch("https://x.test/private/page"))
        self.assertTrue(cache.can_fetch("https://x.test/public"))

    def test_missing_robots_allows(self) -> None:
        cache = RobotsCache(fetcher=lambda _u: None, user_agent="Bot")
        self.assertTrue(cache.can_fetch("https://x.test/anything"))

    def test_fetcher_error_allows(self) -> None:
        def boom(_url: str) -> str:
            raise RuntimeError("network down")

        cache = RobotsCache(fetcher=boom, user_agent="Bot")
        self.assertTrue(cache.can_fetch("https://x.test/anything"))

    def test_crawl_delay(self) -> None:
        text = "User-agent: Bot\nCrawl-delay: 2"
        cache = RobotsCache(fetcher=lambda _u: text, user_agent="Bot")
        self.assertEqual(cache.crawl_delay("https://x.test/"), 2.0)


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.url = "https://x.test/"

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_exc) -> None:
        return None


class TestHttpClient(unittest.TestCase):
    def _client(self, opener, robots_text="") -> HttpClient:
        robots = RobotsCache(fetcher=lambda _u: robots_text or None, user_agent="Bot")
        return HttpClient(user_agent="Bot", robots=robots,
                          limiter=HostRateLimiter(sleep=lambda _s: None),
                          opener=opener, sleep=lambda _s: None)

    def test_success(self) -> None:
        client = self._client(lambda _req: FakeResponse("привет".encode("utf-8")))
        response = client.get("https://x.test/a")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.text, "привет")

    def test_robots_blocks(self) -> None:
        client = self._client(lambda _req: FakeResponse(b"x"),
                              robots_text="User-agent: Bot\nDisallow: /private")
        with self.assertRaises(RobotsDisallowed):
            client.get("https://x.test/private/a")

    def test_retry_then_success(self) -> None:
        calls = {"n": 0}

        def opener(_req):
            calls["n"] += 1
            if calls["n"] < 3:
                raise urllib.error.URLError("temporary")
            return FakeResponse(b"ok")

        client = self._client(opener)
        response = client.get("https://x.test/retry")
        self.assertEqual(response.text, "ok")
        self.assertEqual(calls["n"], 3)

    def test_gives_up(self) -> None:
        def opener(_req):
            raise urllib.error.URLError("always down")

        client = self._client(opener)
        with self.assertRaises(HttpError):
            client.get("https://x.test/dead")


if __name__ == "__main__":
    unittest.main()
