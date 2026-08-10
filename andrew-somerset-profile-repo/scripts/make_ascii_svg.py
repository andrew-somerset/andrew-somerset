#!/usr/bin/env python3
"""Convert a photo into a self-building ASCII portrait (SVG).

Pipeline: rembg cutout -> square crop on the detected face -> bilateral
smooth + unsharp (skin grain becomes wrong characters at this scale) ->
sample onto a 100-column grid -> invert, so DARK pixels get the heavy
glyphs. That inversion is the thing that makes it read as a face: his hair
is the darkest region, so it becomes a solid mass of ink and gives the head
a silhouette, while the lit face stays sparse and its features show as
marks. Mapping bright->heavy instead leaves the hair empty and the portrait
reads as a floating blob. The cut-out background maps to spaces.

Each row flies in from alternating sides, staggered top to bottom, so the
face assembles itself. The stagger lives inside one shared timeline via
keyTimes rather than per-row begin offsets, which means the *static*
attribute values are the finished state: a renderer that ignores SMIL shows
the complete portrait instead of an empty card.

Usage: python scripts/make_ascii_svg.py photo.png
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "andrew-ascii.svg"

RAMP = " .:-=+*oa%#@"           # light -> heavy ink coverage
COLS = int(__import__("os").environ.get("ASCII_COLS", 100))
ROWS = round(COLS * 7.2 / 13)
CHAR_W, CHAR_H = 7.2, 13         # monospace cell, SVG units
FONT_SIZE = 12
GRID_X, GRID_Y = 12, 52          # top-left of the character grid
PAD_BOTTOM = 24
FONT = "SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace"

# On a dark card the glyphs are the light source, so brightness drives BOTH
# glyph density and fill — double-encoding luminance is what makes the face
# read at a glance instead of turning into texture.
TIERS = [(0.34, "#8b949e"), (0.62, "#b1bac4"), (1.01, "#e6edf3")]

INVERT = bool(int(__import__("os").environ.get("ASCII_INVERT", 1)))
CONTRAST_GAMMA = 1.10
INK_FLOOR = 0.11     # nothing inside the cutout is allowed to be blank
FADE_ROWS = 14       # rows over which the shirt dissolves into the card

FLY_IN = 96.0        # px each row travels
TOTAL_S = 3.4        # one shared timeline for every row
ROW_MOVE_S = 0.62    # how long a single row takes to land
ROW_STAGGER_S = 0.042


def square_crop(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, 1.1, 6, minSize=(80, 80))
    h, w = img_bgr.shape[:2]
    if len(faces):
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        side = int(fw * 2.05)
        left, top = fx + fw // 2 - side // 2, int(fy - fh * 0.50)
    else:
        side = int(w * 0.9)
        left, top = (w - side) // 2, int(h * 0.06)
    side = min(side, w, h)
    left = max(0, min(left, w - side))
    top = max(0, min(top, h - side))
    return img_bgr[top:top + side, left:left + side]


def prep(src: Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (ink 0..1 where 1 = darkest, subject mask 0..1) on the grid."""
    from rembg import remove

    img = cv2.imread(str(src))
    if img is None:
        sys.exit(f"could not read {src}")
    crop = square_crop(img)

    rgba = np.array(remove(Image.fromarray(
        cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))).convert("RGBA"))
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0

    gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
    # Smooth skin texture but keep edges: at 100x56 every speck of grain
    # becomes a wrong character, and noise is what destroys the likeness.
    gray = cv2.bilateralFilter(gray, 9, 60, 60)
    blur = cv2.GaussianBlur(gray, (0, 0), gray.shape[0] / 70)
    gray = np.clip(cv2.addWeighted(gray.astype(np.float32), 1.35,
                                   blur.astype(np.float32), -0.35, 0), 0, 255)

    cells = cv2.resize(gray, (COLS, ROWS), interpolation=cv2.INTER_AREA)
    mask = cv2.resize(alpha, (COLS, ROWS), interpolation=cv2.INTER_AREA)

    inside = mask > 0.45
    if inside.any():                       # global stretch over the subject only
        lo, hi = np.percentile(cells[inside], [3, 97])
        cells = np.clip((cells - lo) / max(hi - lo, 1e-6), 0, 1)

    # Tone only. An edge/gradient channel was tried and removed: curly hair
    # has by far the strongest gradients in the frame, so it turned the hair
    # into the densest region and inverted the light logic of the whole card.
    # S-curve deepens the shadows that shape the face and holds the highlights.
    ink = np.clip(cells * cells * (3 - 2 * cells), 0, 1)
    if INVERT:
        ink = 1.0 - ink
    ink = np.power(ink, CONTRAST_GAMMA)

    # Dark hair would otherwise map to spaces and the head would lose its
    # outline entirely, so lift everything inside the cutout off the floor.
    ink = INK_FLOOR + (1 - INK_FLOOR) * ink

    # The white polo is brighter than his face and reads as a solid slab of
    # '@'. Fade it out so the portrait dissolves into the card instead.
    fade = np.ones(ROWS, np.float32)
    tail = np.linspace(1.0, 0.0, FADE_ROWS, dtype=np.float32) ** 1.6
    fade[ROWS - FADE_ROWS:] = tail
    ink *= fade[:, None]
    return np.clip(ink, 0, 1), inside.astype(np.float32)


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def runs(line_chars: list[str], line_tiers: list[int]):
    """Group a row into (text, tier) runs so each row is a handful of tspans."""
    out, buf, cur = [], [], line_tiers[0] if line_tiers else 0
    for ch, t in zip(line_chars, line_tiers):
        if t != cur and buf:
            out.append(("".join(buf), cur))
            buf, cur = [], t
        buf.append(ch)
    if buf:
        out.append(("".join(buf), cur))
    return out


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: make_ascii_svg.py photo.png")
    ink, inside = prep(Path(sys.argv[1]))

    # Build every row first, then drop blank ones off the top and bottom, so
    # a full-width card isn't padded out with empty space it doesn't need.
    grid = []
    for r in range(ROWS):
        chars, tiers = [], []
        for c in range(COLS):
            if inside[r, c] < 0.5 or ink[r, c] <= 0:
                chars.append(" ")
                tiers.append(0)
                continue
            v = float(ink[r, c])
            chars.append(RAMP[min(int(v * len(RAMP)), len(RAMP) - 1)])
            tiers.append(next(i for i, (hi, _) in enumerate(TIERS) if v < hi))
        grid.append((chars, tiers))

    filled = [i for i, (ch, _) in enumerate(grid) if "".join(ch).strip()]
    grid = grid[filled[0]:filled[-1] + 1] if filled else grid
    rows = len(grid)

    w = round(COLS * CHAR_W + 2 * GRID_X)
    h = round(GRID_Y + rows * CHAR_H + PAD_BOTTOM)

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
         f'width="{w}" height="{h}" role="img" aria-label="ASCII portrait of Andrew Somerset">',
         f'<rect width="{w}" height="{h}" rx="8" fill="#0d1117" stroke="#30363d"/>',
         '<circle cx="22" cy="22" r="6" fill="#ff5f56"/>',
         '<circle cx="42" cy="22" r="6" fill="#ffbd2e"/>',
         '<circle cx="62" cy="22" r="6" fill="#27c93f"/>',
         f'<text x="{w - 22}" y="27" text-anchor="end" font-family="{FONT}" '
         f'font-size="12" fill="#7d8590">render --ascii</text>']

    for r, (chars, tiers) in enumerate(grid):
        if not "".join(chars).strip():
            continue

        y = GRID_Y + (r + 1) * CHAR_H - 3
        body = "".join(
            f'<tspan fill="{TIERS[t][1]}">{esc(txt)}</tspan>'
            for txt, t in runs(chars, tiers))

        # stagger encoded as keyTimes on a shared timeline (see module docstring)
        t0 = (r * ROW_STAGGER_S) / TOTAL_S
        t1 = min(t0 + ROW_MOVE_S / TOTAL_S, 0.999)
        dx = FLY_IN if r % 2 else -FLY_IN
        s.append(
            f'<g transform="translate(0,0)" opacity="1">'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="{dx} 0;{dx} 0;0 0;0 0" keyTimes="0;{t0:.4f};{t1:.4f};1" '
            f'calcMode="spline" keySplines="0 0 1 1;0.16 1 0.3 1;0 0 1 1" '
            f'begin="0s" dur="{TOTAL_S}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;0;1;1" '
            f'keyTimes="0;{t0:.4f};{t1:.4f};1" begin="0s" dur="{TOTAL_S}s" fill="freeze"/>'
            f'<text x="{GRID_X}" y="{y}" font-family="{FONT}" font-size="{FONT_SIZE}" '
            f'xml:space="preserve" textLength="{COLS * CHAR_W}" '
            f'lengthAdjust="spacingAndGlyphs">{body}</text></g>')

    s.append("</svg>")
    OUT.write_text("\n".join(s))
    print(f"Wrote {OUT} ({rows}x{COLS}, {w}x{h}, {OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
