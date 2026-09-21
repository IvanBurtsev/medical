"""Соблюдение robots.txt с кэшированием по хосту."""

from __future__ import annotations

import time
import urllib.robotparser
from collections.abc import Callable
from urllib.parse import urljoin, urlparse


class RobotsCache:
    """Кэш правил robots.txt.

    :param fetcher: функция ``(url) -> str | None``; None означает «недоступно».
    :param user_agent: User-Agent, для которого проверяются правила.
    :param ttl: время жизни записи кэша в секундах.
    """

    def __init__(
        self,
        fetcher: Callable[[str], str | None],
        user_agent: str = "*",
        ttl: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetcher = fetcher
        self._user_agent = user_agent
        self._ttl = ttl
        self._clock = clock
        self._cache: dict[str, tuple[urllib.robotparser.RobotFileParser | None, float]] = {}

    def _load(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        cached = self._cache.get(root)
        now = self._clock()
        if cached and now - cached[1] < self._ttl:
            return cached[0]

        robots_url = urljoin(root, "/robots.txt")
        parser: urllib.robotparser.RobotFileParser | None = None
        try:
            text = self._fetcher(robots_url)
        except Exception:
            text = None
        if text:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(text.splitlines())
        self._cache[root] = (parser, now)
        return parser

    def can_fetch(self, url: str) -> bool:
        """Разрешён ли доступ к URL по robots.txt. При отсутствии файла — да."""
        parser = self._load(url)
        if parser is None:
            return True
        return parser.can_fetch(self._user_agent, url)

    def crawl_delay(self, url: str) -> float | None:
        """Директива Crawl-delay для user-agent, если задана."""
        parser = self._load(url)
        if parser is None:
            return None
        delay = parser.crawl_delay(self._user_agent)
        return float(delay) if delay is not None else None
