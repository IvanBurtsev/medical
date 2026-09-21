#!/usr/bin/env python3
"""MedAX Radar — CGI-точка входа дашборда."""
import sys, os, traceback

BASE = os.path.expanduser("~/medax-radar")
sys.path.insert(0, BASE)


def main() -> None:
    from medax_radar.storage import create_repository
    from medax_radar.dashboard import render_html
    from medax_radar import pipeline

    repo = create_repository()
    try:
        if repo.stats()["leads"] == 0:
            pipeline.run(repo=repo, include_competitors=True)
        body = render_html(repo)
    finally:
        repo.close()

    sys.stdout.write("Content-Type: text/html; charset=utf-8\r\n\r\n")
    sys.stdout.write(body)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stdout.write("Content-Type: text/plain; charset=utf-8\r\n\r\n")
        sys.stdout.write("MedAX Radar: internal error\n\n")
        traceback.print_exc(file=sys.stdout)
