"""Веб-дашборд на стандартной библиотеке (http.server)."""

from __future__ import annotations

import base64
import hmac
import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode

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
nav.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}
nav.tabs a{background:var(--card);border:1px solid #24313f;color:#cddcec;padding:8px 14px;
border-radius:10px;text-decoration:none;font-weight:600;font-size:13px}
nav.tabs a.active{background:#21a0ff;color:#04101c;border-color:#21a0ff}
form.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-bottom:16px}
form.filters label{display:flex;flex-direction:column;font-size:11px;color:var(--mut);gap:4px}
form.filters input,form.filters select{background:#13202c;border:1px solid #2a3947;color:var(--ink);
padding:7px 9px;border-radius:8px;font-size:13px;min-width:130px}
form.filters button{background:#21a0ff;color:#04101c;border:0;padding:8px 16px;border-radius:8px;
font-weight:700;cursor:pointer}
form.filters a.export{color:#9fc0e0;font-size:13px;text-decoration:none;padding:8px 12px;
border:1px solid #2a3947;border-radius:8px}
"""


def _badge(tier: str) -> str:
    label = {"hot": "HOT", "warm": "WARM"}.get(tier, tier)
    return f'<span class="badge {html.escape(tier)}">{html.escape(label)}</span>'


def _tags(items: list[str], limit: int = 8) -> str:
    return "".join(f'<span class="tag">{html.escape(x)}</span>' for x in items[:limit])


def parse_filters(query_string: str) -> dict[str, str]:
    """Разбирает строку запроса в словарь фильтров."""
    from urllib.parse import parse_qs

    parsed = parse_qs(query_string or "", keep_blank_values=False)
    return {key: values[0] for key, values in parsed.items() if values and values[0]}


def _contains(text: str, needle: str) -> bool:
    return needle.lower() in (text or "").lower()


def filter_leads(leads: list[dict], filters: dict) -> list[dict]:
    tier, region = filters.get("tier", ""), filters.get("region", "")
    category, query = filters.get("category", ""), filters.get("q", "")
    result = []
    for lead in leads:
        if tier and lead["tier"] != tier:
            continue
        if region and lead["region"] != region:
            continue
        if category and category not in lead["recommended_categories"]:
            continue
        if query and not (_contains(lead["name"], query)
                          or _contains(lead["region"], query)
                          or _contains(lead["city"], query)):
            continue
        result.append(lead)
    return result


def filter_tenders(tenders: list[dict], filters: dict) -> list[dict]:
    region, query = filters.get("region", ""), filters.get("q", "")
    result = []
    for tender in tenders:
        if region and tender["region"] != region:
            continue
        if query and not (_contains(tender["title"], query)
                          or _contains(tender["customer"], query)):
            continue
        result.append(tender)
    return result


def filter_offers(offers: list[dict], filters: dict) -> list[dict]:
    competitor, query = filters.get("competitor", ""), filters.get("q", "")
    result = []
    for offer in offers:
        if competitor and offer["competitor"] != competitor:
            continue
        if query and not _contains(offer["product_name"], query):
            continue
        result.append(offer)
    return result


def _options(values: list[str], selected: str) -> str:
    out = ['<option value="">все</option>']
    for value in sorted(set(values)):
        mark = " selected" if value == selected else ""
        out.append(f'<option value="{html.escape(value)}"{mark}>{html.escape(value)}</option>')
    return "".join(out)


def _filter_form(view: str, filters: dict, export_path: str) -> str:
    q = html.escape(filters.get("q", ""))
    fields = [f'<label>Поиск<input name="q" value="{q}"></label>']
    if view in ("leads", "tenders"):
        fields.append(f'<label>Регион<select name="region">'
                      f'{_options([], filters.get("region", ""))}</select></label>')
    if view == "leads":
        fields.append(
            f'<label>Уровень<select name="tier">'
            f'<option value="">все</option>'
            f'<option value="hot"{" selected" if filters.get("tier") == "hot" else ""}>HOT</option>'
            f'<option value="warm"{" selected" if filters.get("tier") == "warm" else ""}>WARM</option>'
            f'<option value="cold"{" selected" if filters.get("tier") == "cold" else ""}>COLD</option>'
            f'</select></label>')
    if view == "competitors":
        fields.append('<label>Конкурент<select name="competitor">'
                      f'{_options([], filters.get("competitor", ""))}</select></label>')
    export = f'<a class="export" href="{export_path}?type={view}&{urlencode(filters)}">⬇ Excel/CSV</a>'
    return (f'<form class="filters" method="get">'
            f'<input type="hidden" name="view" value="{html.escape(view)}">'
            f'{"".join(fields)}<button type="submit">Фильтр</button>{export}</form>')


def _load_comparison() -> dict | None:
    import json

    from . import config

    path = config.RUNTIME_DIR / "reports" / "price_comparison.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def render_html(db: Repository, filters: dict | None = None,
                export_path: str = "/export") -> str:
    filters = filters or {}
    view = filters.get("view", "leads")
    leads_all = db.leads()
    tenders_all = db.tenders()
    offers_all = db.competitor_offers()
    meta = db.run_meta()
    stats = db.stats()
    hot = sum(1 for x in leads_all if x["tier"] == "hot")
    warm = sum(1 for x in leads_all if x["tier"] == "warm")

    cards = [
        (stats["leads"], "Лидов"), (hot, "HOT"), (warm, "WARM"),
        (stats["clinics"], "Организаций"), (stats["tenders"], "Тендеров"),
        (stats["competitor_offers"], "Предложений конкурентов"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="n">{v}</div><div class="l">{html.escape(l)}</div></div>'
        for v, l in cards
    )

    region_values = [x["region"] for x in leads_all + tenders_all if x.get("region")]
    competitor_values = [o["competitor"] for o in offers_all]
    filter_form = _filter_form(view, filters, export_path)
    # Дополняем select реальными значениями (после построения формы заменяем «все»).
    filter_form = filter_form.replace(
        '<select name="region"><option value="">все</option></select>',
        f'<select name="region">{_options(region_values, filters.get("region", ""))}</select>')
    filter_form = filter_form.replace(
        '<select name="competitor"><option value="">все</option></select>',
        f'<select name="competitor">{_options(competitor_values, filters.get("competitor", ""))}</select>')

    tabs = [
        ("leads", "Лиды"), ("tenders", "Тендеры"),
        ("competitors", "Конкуренты"), ("compare", "Сравнение цен"),
    ]
    tabs_html = "".join(
        f'<a class="{"active" if view == key else ""}" '
        f'href="?view={key}">{html.escape(label)}</a>'
        for key, label in tabs
    )

    body = ""
    if view == "leads":
        leads = filter_leads(leads_all, filters)
        rows = ""
        for lead in leads:
            reasons = "<br>".join(html.escape(r) for r in lead["reasons"][:3])
            rows += (
                f"<tr><td class='score'>{lead['score']}</td><td>{_badge(lead['tier'])}</td>"
                f"<td><b>{html.escape(lead['name'])}</b><div class='reasons'>"
                f"{html.escape(lead['city'])}, {html.escape(lead['region'])}</div></td>"
                f"<td>{_tags(lead['recommended_categories'])}</td>"
                f"<td class='reasons'>{reasons}</td></tr>")
        body = (
            f"<h2>Лиды — показано {len(leads)} из {len(leads_all)}</h2>"
            "<table><tr><th>Балл</th><th>Уровень</th><th>Организация</th>"
            "<th>Категории каталога</th><th>Обоснование</th></tr>"
            f"{rows or '<tr><td colspan=5>Нет данных</td></tr>'}</table>")
    elif view == "tenders":
        tenders = filter_tenders(tenders_all, filters)
        rows = ""
        for t in tenders:
            price = f"{t['price']:,.0f}".replace(",", " ")
            rows += (
                f"<tr><td>{html.escape(t['published_at'])}</td>"
                f"<td>{html.escape(t['region'])}</td><td>{price}</td>"
                f"<td>{_tags(t['matched_categories'], 4)}</td>"
                f"<td class='reasons'>{html.escape(t['customer'])}</td></tr>")
        body = (
            f"<h2>Тендеры — показано {len(tenders)} из {len(tenders_all)}</h2>"
            "<table><tr><th>Публикация</th><th>Регион</th><th>НМЦК, ₽</th>"
            "<th>Категории</th><th>Заказчик</th></tr>"
            f"{rows or '<tr><td colspan=5>Нет данных</td></tr>'}</table>")
    elif view == "competitors":
        offers = filter_offers(offers_all, filters)
        rows = ""
        for o in offers:
            price = f"{o['price']:,.0f}".replace(",", " ")
            rows += (
                f"<tr><td>{html.escape(o['competitor'])}</td>"
                f"<td>{html.escape(o['product_name'])}</td><td>{price}</td>"
                f"<td>{html.escape(o['region'])}</td>"
                f"<td class='reasons'>{html.escape(o['promo'])}</td></tr>")
        body = (
            f"<h2>Предложения конкурентов — показано {len(offers)} из {len(offers_all)}</h2>"
            "<table><tr><th>Конкурент</th><th>Товар</th><th>Цена, ₽</th>"
            "<th>Регион</th><th>Акция</th></tr>"
            f"{rows or '<tr><td colspan=5>Нет данных</td></tr>'}</table>")
    else:
        report = _load_comparison()
        if not report:
            body = ("<h2>Сравнение цен</h2><p class='reasons'>Нет отчёта. "
                    "Запустите: <code>python run.py compare --live</code></p>")
        else:
            pos_rows = "".join(
                f"<tr><td>{html.escape(str(r['category']))}</td><td>{r['pairs']}</td>"
                f"<td>{r['medax_avg']:,.0f}</td><td>{r['competitor_avg']:,.0f}</td>"
                f"<td>{r['delta_pct']:+.1f}%</td></tr>"
                for r in report.get("positioning", []))
            pair_rows = "".join(
                f"<tr><td>{html.escape(str(m['category']))}</td>"
                f"<td>{html.escape(m['medax_name'][:45])}</td><td>{m['medax_price']:,.0f}</td>"
                f"<td>{html.escape(m['competitor'])}</td>"
                f"<td>{html.escape(m['competitor_name'][:40])}</td>"
                f"<td>{m['competitor_price']:,.0f}</td><td>{html.escape(m['cheaper'])}</td></tr>"
                for m in report.get("matches", [])[:50])
            body = (
                "<h2>Позиционирование по категориям</h2>"
                "<table><tr><th>Категория</th><th>Пар</th><th>MedAX, ср.</th>"
                "<th>Конкуренты, ср.</th><th>Δ</th></tr>"
                f"{pos_rows or '<tr><td colspan=5>Нет данных</td></tr>'}</table>"
                "<h2>Пары товаров</h2>"
                "<table><tr><th>Категория</th><th>MedAX</th><th>₽</th><th>Конкурент</th>"
                "<th>Товар</th><th>₽</th><th>Дешевле</th></tr>"
                f"{pair_rows or '<tr><td colspan=7>Уверенных пар нет</td></tr>'}</table>")

    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MedAX Radar — дашборд</title><style>{_STYLE}</style></head><body>
<header><h1>MedAX Radar</h1>
<div class="sub">Рыночная разведка и лид-радар для MedAX Group •
сформировано: {html.escape(meta.get('generated_at', 'н/д'))} • v{html.escape(meta.get('version', ''))}</div>
</header><div class="wrap">
<div class="cards">{cards_html}</div>
<nav class="tabs">{tabs_html}</nav>
{filter_form}
{body}
</div><footer>MedAX Radar v4.0 • данные: открытые реестры и публичные каталоги</footer>
</body></html>"""


def export_csv(db: Repository, type_: str, filters: dict | None = None) -> tuple[str, str]:
    """Возвращает (имя_файла, CSV-текст) для выгрузки в Excel."""
    import csv
    import io

    filters = filters or {}
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    if type_ == "leads":
        writer.writerow(["score", "tier", "name", "region", "city", "phone", "email",
                         "categories", "reasons"])
        for lead in filter_leads(db.leads(), filters):
            writer.writerow([lead["score"], lead["tier"], lead["name"], lead["region"],
                             lead["city"], lead["contacts"].get("phone", ""),
                             lead["contacts"].get("email", ""),
                             ", ".join(lead["recommended_categories"]),
                             " | ".join(lead["reasons"])])
    elif type_ == "tenders":
        writer.writerow(["published_at", "region", "price", "title", "customer", "url"])
        for t in filter_tenders(db.tenders(), filters):
            writer.writerow([t["published_at"], t["region"], t["price"], t["title"],
                             t["customer"], t["url"]])
    elif type_ == "competitors":
        writer.writerow(["competitor", "product_name", "price", "currency", "category",
                         "region", "captured_at", "url"])
        for o in filter_offers(db.competitor_offers(), filters):
            writer.writerow([o["competitor"], o["product_name"], o["price"], o["currency"],
                             o["category"], o["region"], o["captured_at"], o["url"]])
    else:
        raise ValueError(f"Неизвестный тип выгрузки: {type_!r}")
    return f"{type_}.csv", buffer.getvalue()


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

    def _send_csv(self, filename: str, text: str) -> None:
        # utf-8-sig (BOM) — Excel корректно открывает кириллицу.
        data = ("\ufeff" + text).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        from urllib.parse import urlparse

        if not self._authorized():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="MedAX Radar"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        path = urlparse(self.path).path
        filters = parse_filters(urlparse(self.path).query)
        if path.startswith("/health"):
            payload = {"status": "ok", "stats": self.db.stats()}
            self._send(json.dumps(payload, ensure_ascii=False),
                       "application/json; charset=utf-8")
        elif path.startswith("/api/report"):
            payload = {
                "run": self.db.run_meta(),
                "stats": self.db.stats(),
                "leads": self.db.leads(),
                "tenders": self.db.tenders(),
                "competitor_offers": self.db.competitor_offers(),
            }
            self._send(json.dumps(payload, ensure_ascii=False, indent=2),
                       "application/json; charset=utf-8")
        elif path == "/export":
            try:
                filename, text = export_csv(self.db, filters.get("type", "leads"), filters)
            except ValueError:
                self._send("<h1>400 bad export type</h1>", code=400)
                return
            self._send_csv(filename, text)
        elif path in ("/", "/index.html"):
            self._send(render_html(self.db, filters, export_path="/export"))
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
