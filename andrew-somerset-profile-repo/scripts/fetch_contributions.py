#!/usr/bin/env python3
"""Fetch the public GitHub contribution calendar — no token needed.

GitHub serves the same HTML fragment the profile page uses at
https://github.com/users/<username>/contributions
We parse day cells (data-date, data-level) and per-day counts from the
tool-tip elements, then write data/contributions.json with derived stats.
"""
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USERNAME = "andrew-somerset"
URL = f"https://github.com/users/{USERNAME}/contributions"
OUT = Path(__file__).resolve().parent.parent / "data" / "contributions.json"


def fetch_html() -> str:
    resp = requests.get(URL, headers={"User-Agent": "profile-art/1.0"}, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_days(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    # Exact counts live in <tool-tip for="<cell-id>">N contributions on ...</tool-tip>
    counts_by_id: dict[str, int] = {}
    for tip in soup.find_all("tool-tip"):
        target = tip.get("for")
        if not target:
            continue
        m = re.match(r"\s*(\d+|No)\s+contribution", tip.get_text(strip=True))
        if m:
            counts_by_id[target] = 0 if m.group(1) == "No" else int(m.group(1))

    days = []
    for td in soup.find_all("td", class_="ContributionCalendar-day"):
        d = td.get("data-date")
        if not d:
            continue
        level = int(td.get("data-level", 0))
        count = counts_by_id.get(td.get("id", ""), None)
        if count is None:
            # Fallback: approximate from level if tooltip markup ever changes
            count = {0: 0, 1: 1, 2: 4, 3: 8, 4: 12}.get(level, 0)
        days.append({"date": d, "count": count, "level": level})

    days.sort(key=lambda x: x["date"])
    # Drop placeholder cells for future days in the current week
    today = date.today().isoformat()
    return [x for x in days if x["date"] <= today]


def derive_stats(days: list[dict]) -> dict:
    total = sum(d["count"] for d in days)

    # Streaks (consecutive days with >=1 contribution)
    longest = cur = 0
    longest_run = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest_run = max(longest_run, run)
    # Current streak: walk backwards from the most recent day
    for d in reversed(days):
        if d["count"] > 0:
            cur += 1
        else:
            break

    best = max(days, key=lambda d: d["count"], default=None)
    return {
        "total": total,
        "current_streak": cur,
        "longest_streak": longest_run,
        "best_day": {"date": best["date"], "count": best["count"]} if best else None,
    }


def main() -> None:
    html = fetch_html()
    days = parse_days(html)
    if not days:
        print("ERROR: no day cells parsed — GitHub markup may have changed", file=sys.stderr)
        sys.exit(1)
    payload = {
        "username": USERNAME,
        "fetched": date.today().isoformat(),
        "stats": derive_stats(days),
        "days": days,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1))
    print(f"Wrote {OUT} — {len(days)} days, {payload['stats']['total']} contributions")


if __name__ == "__main__":
    main()
