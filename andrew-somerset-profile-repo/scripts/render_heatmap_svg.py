#!/usr/bin/env python3
"""Render data/contributions.json as an animated SVG heatmap.

Classic 53-week x 7-day calendar of rounded boxes. Cells reveal once with a
diagonal slide-down (CSS keyframes inside the SVG — GitHub plays these when
the SVG is embedded via <img>), then freeze. No JS, no external CSS.
"""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "contrib-heatmap.svg"

# none -> brightest (last entry is a neon top end for the best day)
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

CELL, GAP = 11, 4
PITCH = CELL + GAP
LEFT, TOP = 32, 28          # room for day / month labels
FONT = "SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace"
MUTED, TEXT, ACCENT = "#7d8590", "#c9d1d9", "#39d353"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def main() -> None:
    payload = json.loads(DATA.read_text())
    days = payload["days"]
    stats = payload["stats"]
    best_date = (stats.get("best_day") or {}).get("date")

    # Lay out into week columns (weeks start on Sunday, like GitHub)
    cells = []          # (week, weekday, count, level, iso)
    week = 0
    first_wd = (date.fromisoformat(days[0]["date"]).weekday() + 1) % 7  # Sun=0
    for i, d in enumerate(days):
        wd = (first_wd + i) % 7
        if i > 0 and wd == 0:
            week += 1
        cells.append((week, wd, d["count"], d["level"], d["date"]))
    n_weeks = week + 1

    grid_w = n_weeks * PITCH - GAP
    width = LEFT + grid_w + 16
    height = TOP + 7 * PITCH - GAP + 44

    s = []
    s.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-label="{stats["total"]} contributions in the last year">'
    )
    s.append(f"""<style>
 .c{{opacity:0;animation:pop .45s ease-out forwards}}
 @keyframes pop{{from{{opacity:0;transform:translateY(-7px)}}to{{opacity:1;transform:none}}}}
 .t{{opacity:0;animation:fade .6s ease-out forwards}}
 @keyframes fade{{to{{opacity:1}}}}
 text{{font-family:{FONT}}}
</style>""")
    s.append(f'<rect width="{width}" height="{height}" rx="8" fill="#0d1117" stroke="#30363d"/>')

    # Month labels — printed where a new month starts at a week boundary
    seen = None
    for w, wd, *_rest, iso in [(c[0], c[1], c[4]) for c in cells if c[1] == 0]:
        m = int(iso[5:7])
        if m != seen:
            seen = m
            x = LEFT + w * PITCH
            if x < width - 40:
                s.append(f'<text class="t" x="{x}" y="{TOP - 10}" font-size="10" '
                         f'fill="{MUTED}" style="animation-delay:.9s">{MONTHS[m - 1]}</text>')

    # Day labels
    for wd, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        y = TOP + wd * PITCH + CELL - 2
        s.append(f'<text class="t" x="4" y="{y}" font-size="9" fill="{MUTED}" '
                 f'style="animation-delay:.9s">{label}</text>')

    # Cells — diagonal stagger: delay grows with week + weekday
    for w, wd, count, level, iso in cells:
        fill = PALETTE[5] if iso == best_date and count > 0 else PALETTE[min(level, 4)]
        delay = (w + wd) * 14
        s.append(f'<rect class="c" x="{LEFT + w * PITCH}" y="{TOP + wd * PITCH}" '
                 f'width="{CELL}" height="{CELL}" rx="2.5" fill="{fill}" '
                 f'style="animation-delay:{delay}ms"><title>{count} on {iso}</title></rect>')

    # Footer: stats left, legend right
    fy = TOP + 7 * PITCH - GAP + 26
    total = f"{stats['total']:,}"
    footer = (f"{total} contributions in the last year"
              f"  ·  longest streak {stats['longest_streak']}d")
    if stats.get("best_day"):
        footer += f"  ·  best day {stats['best_day']['count']}"
    s.append(f'<text class="t" x="{LEFT}" y="{fy}" font-size="11" fill="{TEXT}" '
             f'style="animation-delay:1.3s"><tspan fill="{ACCENT}">$</tspan> {footer}</text>')

    lx = width - 16 - 5 * PITCH - 66
    s.append(f'<text class="t" x="{lx - 8}" y="{fy}" font-size="10" fill="{MUTED}" '
             f'text-anchor="end" style="animation-delay:1.3s">Less</text>')
    for i in range(5):
        s.append(f'<rect class="c" x="{lx + i * PITCH}" y="{fy - 9}" width="{CELL}" '
                 f'height="{CELL}" rx="2.5" fill="{PALETTE[i]}" '
                 f'style="animation-delay:{1300 + i * 60}ms"/>')
    s.append(f'<text class="t" x="{lx + 5 * PITCH + 4}" y="{fy}" font-size="10" '
             f'fill="{MUTED}" style="animation-delay:1.3s">More</text>')

    s.append("</svg>")
    OUT.write_text("\n".join(s))
    print(f"Wrote {OUT} ({n_weeks} weeks, {len(cells)} cells)")


if __name__ == "__main__":
    main()
