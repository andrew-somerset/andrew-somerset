#!/usr/bin/env python3
"""Build portrait.svg — a real photo in the same terminal card as info-card.svg.

Steps:
  1. Face-detect and crop the source photo to a square with headroom
  2. Cut the subject out of its background (rembg) and composite onto the
     card's #0d1117 so the portrait sits *in* the terminal, not on a white box
  3. Emit an SVG card (chrome bar + rounded photo) with the PNG inlined as
     base64, so the README needs exactly one file and no external hosting

Usage: python scripts/make_portrait_card.py source-photo.png
Writes portrait.svg next to the repo root.
"""
import base64
import io
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_SVG = ROOT / "portrait.svg"

# --- card geometry (matches info-card.svg's 8px radius / 22px gutter) --------
CARD_W, CARD_H = 370, 400
PAD = 22
PHOTO_X, PHOTO_Y = PAD, 52
PHOTO_W = CARD_W - 2 * PAD          # 326
PHOTO_H = PHOTO_W                   # square
SCALE = 2                           # render the bitmap at 2x for retina

BG = (13, 17, 23)                   # #0d1117
GLOW = (57, 211, 83)                # #39d353


def square_crop(img_bgr: np.ndarray) -> np.ndarray:
    """Crop to a square centred on the face, with headroom above the hair."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(gray, 1.1, 6, minSize=(80, 80))
    h, w = img_bgr.shape[:2]

    if len(faces):
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        side = int(fw * 2.7)
        cx = fx + fw // 2
        top = int(fy - fh * 0.62)
        left = cx - side // 2
    else:                                        # centred fallback
        side = int(w * 0.92)
        left, top = (w - side) // 2, int(h * 0.06)

    side = min(side, w, h)
    left = max(0, min(left, w - side))
    top = max(0, min(top, h - side))
    return img_bgr[top:top + side, left:left + side]


def cutout(img_bgr: np.ndarray) -> Image.Image:
    """Return an RGBA PIL image with the background removed."""
    from rembg import remove

    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return remove(Image.fromarray(rgb)).convert("RGBA")


def aura_plate(size: tuple[int, int]) -> np.ndarray:
    """Dark background with a soft radial glow sitting behind the head."""
    w, h = size
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    # centre the glow on the head, not the frame
    d = np.sqrt(((xs - w * 0.50) / (w * 0.46)) ** 2 +
                ((ys - h * 0.40) / (h * 0.44)) ** 2)
    falloff = np.clip(1.0 - d, 0.0, 1.0) ** 1.9        # smooth, no banding
    a = (falloff * 0.20)[..., None]                     # peak ~20% green
    return (np.array(BG, np.float32) * (1 - a) +
            np.array(GLOW, np.float32) * a).astype(np.uint8)


def build_photo_jpeg(src: Path) -> bytes:
    """Subject on the terminal background, as a JPEG (SVG rounds the corners)."""
    img = cv2.imread(str(src))
    if img is None:
        sys.exit(f"could not read {src}")

    size = (PHOTO_W * SCALE, PHOTO_H * SCALE)
    subject = cutout(square_crop(img)).resize(size, Image.LANCZOS)

    plate = Image.fromarray(aura_plate(size)).convert("RGBA")
    plate.alpha_composite(subject)

    buf = io.BytesIO()
    plate.convert("RGB").save(buf, format="JPEG", quality=90,
                              subsampling=0, optimize=True, progressive=True)
    return buf.getvalue()


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: make_portrait_card.py photo.png")

    b64 = base64.b64encode(build_photo_jpeg(Path(sys.argv[1]))).decode()

    # NOTE: opacity defaults to 1 and is animated via SMIL, so a renderer that
    # ignores animation still shows the photo instead of a blank card.
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {CARD_W} {CARD_H}" width="{CARD_W}" height="{CARD_H}" role="img" aria-label="Portrait of Andrew Somerset">
<clipPath id="ph"><rect x="{PHOTO_X}" y="{PHOTO_Y}" width="{PHOTO_W}" height="{PHOTO_H}" rx="6"/></clipPath>
<rect width="{CARD_W}" height="{CARD_H}" rx="8" fill="#0d1117" stroke="#30363d"/>
<circle cx="22" cy="22" r="6" fill="#ff5f56"/>
<circle cx="42" cy="22" r="6" fill="#ffbd2e"/>
<circle cx="62" cy="22" r="6" fill="#27c93f"/>
<text x="{CARD_W - PAD + 6}" y="27" text-anchor="end" font-family="SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace" font-size="12" fill="#7d8590">portrait.jpg</text>
<image x="{PHOTO_X}" y="{PHOTO_Y}" width="{PHOTO_W}" height="{PHOTO_H}" clip-path="url(#ph)" preserveAspectRatio="xMidYMid slice" xlink:href="data:image/jpeg;base64,{b64}"><animate attributeName="opacity" from="0" to="1" begin="0s" dur="0.7s" fill="freeze"/></image>
<rect x="{PHOTO_X}" y="{PHOTO_Y}" width="{PHOTO_W}" height="{PHOTO_H}" rx="6" fill="none" stroke="#30363d"/>
</svg>
'''
    OUT_SVG.write_text(svg)
    print(f"Wrote {OUT_SVG} ({OUT_SVG.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
