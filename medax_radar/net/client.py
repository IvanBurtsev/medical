"""HTTP-клиент с соблюдением robots.txt, rate limiting и ретраями.

Все зависимости (opener, sleep, robots, limiter) инжектируются — это делает
клиент полностью тестируемым без сети.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import Message

from .ratelimit import HostRateLimiter
from .robots import RobotsCache


class HttpError(RuntimeError):
    """Ошибка HTTP после исчерпания ретраев."""


class RobotsDisallowed(RuntimeError):
    """Доступ запрещён правилами robots.txt."""


@dataclass
class HttpResponse:
    url: str
    status: int
    text: str
    headers: dict[str, str] = field(default_factory=dict)


def _default_opener(request: urllib.request.Request):
    return urllib.request.urlopen(request, timeout=30)  # noqa: S310


class HttpClient:
    """Клиент для забора публичных страниц и API."""

    def __init__(
        self,
        user_agent: str = "MedAXRadarBot/4.0",
        robots: RobotsCache | None = None,
        limiter: HostRateLimiter | None = None,
        opener: Callable = _default_opener,
        retries: int = 3,
        backoff_base: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
        respect_robots: bool = True,
    ) -> None:
        self.user_agent = user_agent
        self.robots = robots or RobotsCache(fetcher=lambda _url: None, user_agent=user_agent)
        self.limiter = limiter or HostRateLimiter()
        self._opener = opener
        self.retries = max(1, retries)
        self.backoff_base = backoff_base
        self._sleep = sleep
        self.respect_robots = respect_robots

    def get(self, url: str) -> HttpResponse:
        """Забирает URL. Бросает RobotsDisallowed / HttpError."""
        if self.respect_robots and not self.robots.can_fetch(url):
            raise RobotsDisallowed(f"robots.txt запрещает доступ: {url}")

        delay = self.robots.crawl_delay(url)
        if delay:
            self._sleep(delay)
        self.limiter.acquire(url)

        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
                with self._opener(request) as response:
                    body = response.read()
                    charset = self._charset(response.headers)
                    text = body.decode(charset, errors="replace")
                    return HttpResponse(
                        url=getattr(response, "url", url),
                        status=getattr(response, "status", 200),
                        text=text,
                        headers=dict(response.headers),
                    )
            except urllib.error.HTTPError as exc:  # pragma: no cover - сеть
                last_error = exc
                if exc.code in (429, 500, 502, 503, 504):
                    self._sleep(self.backoff_base * (2**attempt))
                    continue
                raise HttpError(f"HTTP {exc.code} для {url}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover
                last_error = exc
                self._sleep(self.backoff_base * (2**attempt))
        raise HttpError(f"Не удалось забрать {url}: {last_error}")

    @staticmethod
    def _charset(headers: Message | dict) -> str:
        try:
            content_type = headers.get("Content-Type", "") if headers else ""
        except AttributeError:
            return "utf-8"
        if content_type and "charset=" in content_type:
            return content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        return "utf-8"
