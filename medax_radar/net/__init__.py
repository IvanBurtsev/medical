"""Сетевой слой: rate limiting, robots.txt и HTTP-клиент.

Слой изолирован и тестируем: часы, sleep и opener инжектируются.
Используется адаптерами в live-режиме; демо работает офлайн.
"""

from .ratelimit import HostRateLimiter, RateLimiter
from .robots import RobotsCache
from .client import HttpClient, HttpResponse

__all__ = [
    "RateLimiter",
    "HostRateLimiter",
    "RobotsCache",
    "HttpClient",
    "HttpResponse",
]
