#!/usr/bin/env python3
"""MedAX Radar — выгрузка CSV (Excel) через CGI."""
import sys, os, traceback

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_7m2k9x")
if not os.path.isdir(BASE):
    BASE = os.path.expanduser("~/medax-radar")
sys.path.insert(0, BASE)


def main() -> None:
    from medax_radar.storage import create_repository
    from medax_radar.dashboard import export_csv, parse_filters

    filters = parse_filters(os.environ.get("QUERY_STRING", ""))
    repo = create_repository()
    try:
        filename, text = export_csv(repo, filters.get("type", "leads"), filters)
    finally:
        repo.close()

    data = ("\ufeff" + text).encode("utf-8")
    sys.stdout.write("Content-Type: text/csv; charset=utf-8\r\n")
    sys.stdout.write(f'Content-Disposition: attachment; filename="{filename}"\r\n\r\n')
    sys.stdout.flush()
    sys.stdout.buffer.write(data)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stdout.write("Content-Type: text/plain; charset=utf-8\r\n\r\n")
        traceback.print_exc(file=sys.stdout)
