#!/usr/bin/env python3
"""MedAX Radar — JSON API (CGI)."""
import sys, os, json, traceback

BASE = os.path.expanduser("~/medax-radar")
sys.path.insert(0, BASE)


def main() -> None:
    from medax_radar.storage import create_repository
    from medax_radar import pipeline

    repo = create_repository()
    try:
        if repo.stats()["leads"] == 0:
            pipeline.run(repo=repo, include_competitors=True)
        payload = {
            "run": repo.run_meta(),
            "stats": repo.stats(),
            "leads": repo.leads(),
            "tenders": repo.tenders(),
            "competitor_offers": repo.competitor_offers(),
        }
    finally:
        repo.close()

    sys.stdout.write("Content-Type: application/json; charset=utf-8\r\n\r\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stdout.write("Content-Type: text/plain; charset=utf-8\r\n\r\n")
        traceback.print_exc(file=sys.stdout)
