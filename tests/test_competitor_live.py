"""Интеграционный тест live-сбора конкурента через локальный HTTP-сервер."""

from __future__ import annotations

import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from medax_radar.ingestion.competitor import scrape_url  # noqa: E402

PAGE = """<!doctype html><html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Компрессор Mercury 70л",
 "offers":{"@type":"Offer","price":"23500","priceCurrency":"RUB"}}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Матрас 3+1",
 "offers":{"@type":"Offer","price":"49000","priceCurrency":"RUB"}}
</script>
</head><body>каталог</body></html>
"""

ROBOTS = "User-agent: *\nAllow: /\n"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/robots.txt":
            body = ROBOTS.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
        elif self.path.startswith("/catalog"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            self.send_response(404)
            body = b"not found"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


class TestLiveScrape(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def test_scrape_extracts_jsonld_offers(self) -> None:
        url = f"http://127.0.0.1:{self.port}/catalog/"
        offers = scrape_url(url, "Локальный конкурент", region="Ставропольский край")
        names = {o["product_name"] for o in offers}
        self.assertIn("Компрессор Mercury 70л", names)
        self.assertIn("Матрас 3+1", names)
        prices = {o["price"] for o in offers}
        self.assertEqual(prices, {23500.0, 49000.0})
        self.assertTrue(all(o["competitor"] == "Локальный конкурент" for o in offers))

    def test_robots_disallow_blocks(self) -> None:
        # Отдельный сервер, запрещающий всё.
        class DisallowHandler(_Handler):
            def do_GET(self) -> None:  # noqa: N802
                body = b"User-agent: *\nDisallow: /\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), DisallowHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(Exception):
                scrape_url(f"http://127.0.0.1:{port}/catalog/", "K")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
