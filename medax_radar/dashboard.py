"""Веб-дашборд на стандартной библиотеке (http.server)."""

from __future__ import annotations

import base64
import hmac
import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .storage import Repository, create_repository

#: Публичный путь, не требующий аутентификации (для healthcheck).
PUBLIC_PATHS = ("/health",)


def check_basic_auth(header: str | None, user: str, password: str) -> bool:
    """Проверяет HTTP Basic Authorization.

    Если пользователь не задан — доступ открыт (возвращает True).
    """
    if not user:
        return True
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:].strip()).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    given_user, sep, given_password = decoded.partition(":")
    if not sep:
        return False
    return hmac.compare_digest(given_user, user) and hmac.compare_digest(
        given_password, password
    )

_STYLE = """
:root{--bg:#0f1720;--card:#1b2733;--ink:#e8eef5;--mut:#8fa3b8;--hot:#ff5c7a;
--warm:#ffb020;--cold:#5a7085;--acc:#21a0ff;--ok:#2ecc71}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif}
header{padding:22px 28px;background:linear-gradient(90deg,#132234,#0f1720);
border-bottom:1px solid #24313f}header h1{margin:0;font-size:20px}
header .sub{color:var(--mut);font-size:12px;margin-top:4px}
.wrap{padding:22px 28px;max-width:1180px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:22px}
.card{background:var(--card);border:1px solid #24313f;border-radius:12px;padding:16px}
.card .n{font-size:28px;font-weight:700}.card .l{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
h2{font-size:15px;margin:26px 0 10px;color:#cddcec}
table{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #24313f;font-size:13px;vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700}
.hot{background:rgba(255,92,122,.16);color:var(--hot)}
.warm{background:rgba(255,176,32,.16);color:var(--warm)}
.cold{background:rgba(90,112,133,.18);color:#a9bccd}
.score{font-weight:700}.tag{display:inline-block;background:#22303e;color:#9fc0e0;
padding:1px 7px;border-radius:6px;font-size:11px;margin:1px 2px 1px 0}
.reasons{color:var(--mut);font-size:12px}
footer{color:var(--mut);font-size:12px;padding:20px 28px;text-align:center}
"""


def _badge(tier: str) -> str:
    label = {"hot": "HOT", "warm": "WARM"}.get(tier, tier)
    return f'<span class="badge {html.escape(tier)}">{html.escape(label)}</span>'


def _tags(items: list[str], limit: int = 8) -> str:
    return "".join(f'<span class="tag">{html.escape(x)}</span>' for x in items[:limit])


def render_html(db: Repository) -> str:
    leads = db.leads()
    tenders = db.tenders()
    offers = db.competitor_offers()
    meta = db.run_meta()
    stats = db.stats()
    hot = sum(1 for x in leads if x["tier"] == "hot")
    warm = sum(1 for x in leads if x["tier"] == "warm")

    cards = [
        (stats["leads"], "Лидов"),
        (hot, "HOT"),
        (warm, "WARM"),
        (stats["clinics"], "Организаций"),
        (stats["tenders"], "Тендеров"),
        (stats["competitor_offers"], "Предложений конкурентов"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="n">{v}</div><div class="l">{html.escape(l)}</div></div>'
        for v, l in cards
    )

    lead_rows = ""
    for lead in leads:
        reasons = "<br>".join(html.escape(r) for r in lead["reasons"][:3])
        lead_rows += (
            f"<tr><td class='score'>{lead['score']}</td><td>{_badge(lead['tier'])}</td>"
            f"<td><b>{html.escape(lead['name'])}</b><div class='reasons'>"
            f"{html.escape(lead['city'])}, {html.escape(lead['region'])}</div></td>"
            f"<td>{_tags(lead['recommended_categories'])}</td>"
            f"<td class='reasons'>{reasons}</td></tr>"
        )

    tender_rows = ""
    for t in tenders:
        price = f"{t['price']:,.0f}".replace(",", " ")
        tender_rows += (
            f"<tr><td>{html.escape(t['published_at'])}</td>"
            f"<td>{html.escape(t['region'])}</td><td>{price}</td>"
            f"<td>{_tags(t['matched_categories'], 4)}</td>"
            f"<td class='reasons'>{html.escape(t['customer'])}</td></tr>"
        )

    offer_rows = ""
    for o in offers:
        price = f"{o['price']:,.0f}".replace(",", " ")
        offer_rows += (
            f"<tr><td>{html.escape(o['competitor'])}</td>"
            f"<td>{html.escape(o['product_name'])}</td><td>{price}</td>"
            f"<td>{html.escape(o['region'])}</td>"
            f"<td class='reasons'>{html.escape(o['promo'])}</td></tr>"
        )

    offers_block = ""
    if offer_rows:
        offers_block = (
            "<h2>Предложения конкурентов (модуль 2)</h2><table>"
            "<tr><th>Конкурент</th><th>Товар</th><th>Цена, ₽</th>"
            "<th>Регион</th><th>Акция</th></tr>"
            f"{offer_rows}</table>"
        )

    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MedAX Radar — дашборд</title><style>{_STYLE}</style></head><body>
<header><h1>MedAX Radar</h1>
<div class="sub">Рыночная разведка и лид-радар для MedAX Group •
сформировано: {html.escape(meta.get('generated_at', 'н/д'))} • v{html.escape(meta.get('version', ''))}</div>
</header><div class="wrap">
<div class="cards">{cards_html}</div>
<h2>Лиды (топ по скорингу)</h2>
<table><tr><th>Балл</th><th>Уровень</th><th>Организация</th>
<th>Категории каталога</th><th>Обоснование</th></tr>{lead_rows or '<tr><td colspan=5>Нет данных</td></tr>'}</table>
<h2>Активные тендеры</h2>
<table><tr><th>Публикация</th><th>Регион</th><th>НМЦК, ₽</th>
<th>Категории</th><th>Заказчик</th></tr>{tender_rows or '<tr><td colspan=5>Нет данных</td></tr>'}</table>
{offers_block}
</div><footer>MedAX Radar v4.0 • demo • API: <code>/api/report</code></footer>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    db: Repository
    auth_user: str = ""
    auth_password: str = ""

    def _send(self, body: str, ctype: str = "text/html; charset=utf-8", code: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        if any(self.path.startswith(p) for p in PUBLIC_PATHS):
            return True
        return check_basic_auth(
            self.headers.get("Authorization"), self.auth_user, self.auth_password
        )

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="MedAX Radar"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path.startswith("/health"):
            payload = {"status": "ok", "stats": self.db.stats()}
            self._send(json.dumps(payload, ensure_ascii=False),
                       "application/json; charset=utf-8")
        elif self.path.startswith("/api/report"):
            payload = {
                "run": self.db.run_meta(),
                "stats": self.db.stats(),
                "leads": self.db.leads(),
                "tenders": self.db.tenders(),
                "competitor_offers": self.db.competitor_offers(),
            }
            self._send(json.dumps(payload, ensure_ascii=False, indent=2),
                       "application/json; charset=utf-8")
        elif self.path in ("/", "/index.html"):
            self._send(render_html(self.db))
        else:
            self._send("<h1>404</h1>", code=404)

    def log_message(self, *_args) -> None:  # quiet
        return


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    db = create_repository()
    if db.stats()["leads"] == 0:
        print("БД пуста. Сначала выполните: python run.py run --competitors")
    auth_user = os.environ.get("MEDAX_AUTH_USER", "")
    auth_password = os.environ.get("MEDAX_AUTH_PASSWORD", "")
    handler = type("BoundHandler", (_Handler,), {
        "db": db, "auth_user": auth_user, "auth_password": auth_password,
    })
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"Дашборд доступен: http://{host}:{port}")
    if auth_user:
        print(f"Доступ защищён HTTP Basic (пользователь: {auth_user})")
    else:
        print("ВНИМАНИЕ: аутентификация выключена (MEDAX_AUTH_USER не задан)")
    print("Остановка: Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        httpd.server_close()
        db.close()
