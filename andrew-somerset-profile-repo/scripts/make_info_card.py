#!/usr/bin/env python3
"""Hand-author the neofetch-style info card SVG.

Each line fades + slides in on a short stagger, plays once, freezes.
Set STATIC=1 to emit a frozen frame (handy for local Quick Look previews).
"""
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "info-card.svg"
STATIC = os.environ.get("STATIC") == "1"

FONT = "SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace"
GREEN, CYAN, YELLOW = "#39d353", "#58a6ff", "#e3b341"
TEXT, MUTED = "#c9d1d9", "#7d8590"

# (key, value) — key colored, value plain. None key = plain line, "" = spacer.
LINES = [
    ("header", "andrew@github"),
    ("rule", "-------------"),
    ("Now", "Analytics + CS @ Columbia Engineering"),
    ("Focus", "AI systems for better decisions"),
    ("Base", "New York City"),
    ("", ""),
    ("Building", "blue_pill — an autonomous agent given"),
    (None, "         $100 of compute to stay alive"),
    ("Research", "ML for smart manufacturing (w/ Dr. Zhang)"),
    ("", ""),
    ("Stack", "Python · PyTorch · pandas · scikit-learn"),
    (None, "         Gurobi/OR · TypeScript · React · SQL"),
    ("", ""),
    ("Links", "linkedin.com/in/andrew-somerset"),
    (None, "         x.com/AndrewSomerset_"),
]

W, LINE_H, PAD_TOP, PAD_LEFT = 454, 22, 56, 22
H = PAD_TOP + LINE_H * len(LINES) + 14


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
         f'width="{W}" height="{H}" role="img" aria-label="About Andrew Somerset">']
    anim = "" if STATIC else """<style>
 .l{opacity:0;animation:in .5s ease-out forwards}
 @keyframes in{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}
</style>"""
    if anim:
        s.append(anim)
    s.append(f'<rect width="{W}" height="{H}" rx="8" fill="#0d1117" stroke="#30363d"/>')
    # Title bar: traffic-light dots
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        s.append(f'<circle cx="{22 + i * 20}" cy="22" r="6" fill="{c}"/>')
    s.append(f'<text x="{W - 20}" y="27" text-anchor="end" font-family="{FONT}" '
             f'font-size="12" fill="{MUTED}">neofetch</text>')

    for i, (key, val) in enumerate(LINES):
        y = PAD_TOP + (i + 1) * LINE_H - 6
        cls = "" if STATIC else ' class="l"'
        delay = "" if STATIC else f' style="animation-delay:{200 + i * 130}ms"'
        if key == "" and val == "":
            continue
        if key == "header":
            s.append(f'<text{cls} x="{PAD_LEFT}" y="{y}" font-family="{FONT}" '
                     f'font-size="14" font-weight="bold" fill="{GREEN}"{delay}>'
                     f'{esc(val)}</text>')
        elif key == "rule":
            s.append(f'<text{cls} x="{PAD_LEFT}" y="{y}" font-family="{FONT}" '
                     f'font-size="14" fill="{MUTED}"{delay}>{esc(val)}</text>')
        elif key is None:
            s.append(f'<text{cls} x="{PAD_LEFT}" y="{y}" font-family="{FONT}" '
                     f'font-size="13" fill="{TEXT}" xml:space="preserve"{delay}>'
                     f'{esc(val)}</text>')
        else:
            s.append(f'<text{cls} x="{PAD_LEFT}" y="{y}" font-family="{FONT}" '
                     f'font-size="13" xml:space="preserve"{delay}>'
                     f'<tspan fill="{CYAN}" font-weight="bold">{key}</tspan>'
                     f'<tspan fill="{MUTED}">{"." * max(1, 9 - len(key))}</tspan> '
                     f'<tspan fill="{TEXT}">{esc(val)}</tspan></text>')

    # Blinking block cursor on the last line (subtle infinite blink is the one
    # loop we keep — it reads as "terminal is live")
    cy = PAD_TOP + (len(LINES) + 1) * LINE_H - 16
    blink = '' if STATIC else (f'<animate attributeName="opacity" values="1;0;1" '
                               f'dur="1.2s" begin="{(200 + len(LINES) * 130) / 1000}s" '
                               f'repeatCount="indefinite"/>')
    s.append(f'<rect x="{PAD_LEFT}" y="{cy}" width="9" height="16" fill="{GREEN}">'
             f'{blink}</rect>')
    s.append("</svg>")
    OUT.write_text("\n".join(s))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
