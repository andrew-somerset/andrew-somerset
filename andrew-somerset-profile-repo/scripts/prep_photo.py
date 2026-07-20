#!/usr/bin/env python3
"""Prep a photo for ASCII conversion. Run once per photo (local only).

1. Isolate the subject (rembg if installed, else OpenCV GrabCut fallback)
2. Boost local contrast with CLAHE — gives a flat face real highlights/shadows
3. Composite onto pure white so the background maps to spaces in the ramp

Usage: python scripts/prep_photo.py source-photo.jpg [x y w h]
Optional x y w h crops first (useful to cut one person out of a group shot).
Writes source-prepped.png next to this script's repo root.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).resolve().parent.parent / "source-prepped.png"


def remove_bg(img_bgr: np.ndarray) -> np.ndarray:
    """Return BGRA with background transparent."""
    try:
        from rembg import remove  # optional heavy dep

        rgba = remove(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        return cv2.cvtColor(np.array(rgba), cv2.COLOR_RGBA2BGRA)
    except ImportError:
        print("rembg not installed — falling back to GrabCut")
        h, w = img_bgr.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        rect = (int(w * 0.06), int(h * 0.03), int(w * 0.88), int(h * 0.94))
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(img_bgr, mask, rect, bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
        alpha = np.where((mask == 2) | (mask == 0), 0, 255).astype(np.uint8)
        alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
        out = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2BGRA)
        out[:, :, 3] = alpha
        return out


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: prep_photo.py photo.jpg [x y w h]")
    img = cv2.imread(sys.argv[1])
    if img is None:
        sys.exit(f"could not read {sys.argv[1]}")
    if len(sys.argv) == 6:
        x, y, w, h = map(int, sys.argv[2:6])
        img = img[y:y + h, x:x + w]

    bgra = remove_bg(img)

    # CLAHE on the luminance channel
    gray = cv2.cvtColor(bgra[:, :, :3], cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Composite onto pure white using the alpha matte
    alpha = bgra[:, :, 3].astype(np.float32) / 255.0
    comp = (gray.astype(np.float32) * alpha + 255.0 * (1 - alpha)).astype(np.uint8)

    cv2.imwrite(str(OUT), comp)
    print(f"Wrote {OUT} ({comp.shape[1]}x{comp.shape[0]})")


if __name__ == "__main__":
    main()
