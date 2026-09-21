"""Адаптивный rate limiting: token bucket на хост.

Часы и sleep инжектируются, чтобы поведение было детерминированным в тестах.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import urlparse


class RateLimiter:
    """Token bucket.

    :param rate_per_sec: пополнение токенов в секунду.
    :param burst: максимальный запас токенов (размер всплеска).
    """

    def __init__(
        self,
        rate_per_sec: float = 1.0,
        burst: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec должен быть больше нуля")
        if burst < 1:
            raise ValueError("burst должен быть не меньше 1")
        self.rate = float(rate_per_sec)
        self.burst = float(burst)
        self._tokens = float(burst)
        self._clock = clock
        self._sleep = sleep
        self._last = clock()

    def acquire(self, tokens: float = 1.0) -> float:
        """Блокирует до появления токенов. Возвращает время ожидания (сек)."""
        if tokens > self.burst:
            raise ValueError("Запрошено токенов больше, чем вмещает bucket")
        now = self._clock()
        self._tokens = min(self.burst, self._tokens + (now - self._last) * self.rate)
        self._last = now
        waited = 0.0
        if self._tokens < tokens:
            deficit = tokens - self._tokens
            waited = deficit / self.rate
            self._sleep(waited)
            self._tokens = 0.0
            self._last = self._clock()
        else:
            self._tokens -= tokens
        return waited


class HostRateLimiter:
    """Rate limiter с отдельным bucket на каждый хост."""

    def __init__(
        self,
        rate_per_sec: float = 1.0,
        burst: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._rate = rate_per_sec
        self._burst = burst
        self._clock = clock
        self._sleep = sleep
        self._limiters: dict[str, RateLimiter] = {}

    def limiter_for(self, url: str) -> RateLimiter:
        host = urlparse(url).netloc.lower() or "_"
        if host not in self._limiters:
            self._limiters[host] = RateLimiter(
                rate_per_sec=self._rate,
                burst=self._burst,
                clock=self._clock,
                sleep=self._sleep,
            )
        return self._limiters[host]

    def acquire(self, url: str, tokens: float = 1.0) -> float:
        return self.limiter_for(url).acquire(tokens)
