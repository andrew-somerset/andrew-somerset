#!/usr/bin/env python3
"""Convert source-prepped.png into a self-typing monochrome ASCII SVG.

Each row is wrapped in a horizontal clip that wipes left-to-right with a
small block cursor riding the wipe edge, staggered top to bottom. Prints
once and freezes. SMIL inside the SVG — GitHub plays it via <img>.
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-prepped.png"
OUT = ROOT / "andrew-ascii.svg"

RAMP = " .`:-=+*cs#%@"   # bright (sparse) -> dark (dense); space clears bg
COLS = 100               # character grid width (rows follow aspect ratio)
CHAR_W, CHAR_H = 7.2, 13  # monospace cell in SVG units
FILL = "#c9d1d9"          # one light-gray fill — monochrome on purpose
FONT = "SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace"
ROW_STAGGER_S = 0.055     # delay between rows starting
WIPE_S = 0.5              # duration of each row's wipe


def to_grid(img: Image.Image) -> list[str]:
    # Characters are taller than wide -> squash rows by the cell aspect ratio
    rows = max(1, round(img.height / img.width * COLS * (CHAR_W / CHAR_H)))
    g = np.asarray(img.convert("L").resize((COLS, rows), Image.LANCZOS), dtype=float)
    idx = ((255.0 - g) / 255.0 * (len(RAMP) - 1)).round().astype(int)
    return ["".join(RAMP[i] for i in r).rstrip() for r in idx]


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    lines = to_grid(Image.open(SRC))
    w = round(COLS * CHAR_W + 24)
    h = round(len(lines) * CHAR_H + 24)

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
         f'width="{w}" height="{h}" role="img" aria-label="ASCII portrait">']
    s.append(f'<rect width="{w}" height="{h}" rx="8" fill="#0d1117" stroke="#30363d"/>')

    for i, line in enumerate(lines):
        if not line:
            continue
        y = 12 + (i + 1) * CHAR_H - 3
        begin = i * ROW_STAGGER_S
        clip_id = f"r{i}"
        # Clip rect wipes from width 0 -> full row width
        s.append(f'<clipPath id="{clip_id}"><rect x="12" y="{y - CHAR_H}" '
                 f'width="0" height="{CHAR_H + 2}">'
                 f'<animate attributeName="width" from="0" to="{w - 24}" '
                 f'begin="{begin:.3f}s" dur="{WIPE_S}s" fill="freeze"/></rect></clipPath>')
        s.append(f'<text x="12" y="{y}" clip-path="url(#{clip_id})" '
                 f'font-family="{FONT}" font-size="12" xml:space="preserve" '
                 f'fill="{FILL}" textLength="{COLS * CHAR_W}" '
                 f'lengthAdjust="spacingAndGlyphs">{esc(line.ljust(COLS))}</text>')
        # Block cursor rides the wipe edge, then vanishes
        s.append(f'<rect x="12" y="{y - CHAR_H + 3}" width="{CHAR_W}" height="{CHAR_H}" '
                 f'fill="{FILL}" opacity="0">'
                 f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.02;0.98;1" '
                 f'begin="{begin:.3f}s" dur="{WIPE_S}s" fill="freeze"/>'
                 f'<animate attributeName="x" from="12" to="{w - 12 - CHAR_W}" '
                 f'begin="{begin:.3f}s" dur="{WIPE_S}s" fill="freeze"/></rect>')

    s.append("</svg>")
    OUT.write_text("\n".join(s))
    print(f"Wrote {OUT} ({len(lines)} rows x {COLS} cols)")


if __name__ == "__main__":
    main()
