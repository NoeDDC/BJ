"""One-off script that (re)generates the app icons under public/icons/.

Not needed at runtime — only run this manually when the mark/colors change:
    python scripts/generate_icons.py
"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "public", "icons")

SCALE = 4  # supersample factor for crisp anti-aliased edges

INK  = (28, 24, 20, 255)    # --ink
Z    = (139, 62, 47, 255)   # --z
N    = (43, 95, 107, 255)   # --n
GOLD = (201, 150, 46, 255)  # --gold


def draw_mark(size, safe_ratio):
    """Dark square background with two overlapping circles (Z / N) joined
    by a small gold dot in the middle — echoes the calendar's 'both free'
    star. safe_ratio controls how large the mark is relative to the canvas
    (smaller = more padding, used for maskable icons)."""
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s, s], fill=INK)

    cx, cy = s / 2, s / 2
    r = s * safe_ratio / 2 * 0.62
    gap = r * 0.32

    lcx = cx - r - gap / 2
    rcx = cx + r + gap / 2

    d.ellipse([lcx - r, cy - r, lcx + r, cy + r], fill=Z)
    d.ellipse([rcx - r, cy - r, rcx + r, cy + r], fill=N)

    gr = gap / 2 + r * 0.22
    d.ellipse([cx - gr, cy - gr, cx + gr, cy + gr], fill=GOLD)

    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    draw_mark(512, 0.82).save(os.path.join(OUT, "icon-512.png"))
    draw_mark(192, 0.82).save(os.path.join(OUT, "icon-192.png"))
    draw_mark(512, 0.55).save(os.path.join(OUT, "icon-maskable-512.png"))
    draw_mark(180, 0.86).save(os.path.join(OUT, "apple-touch-icon.png"))
    draw_mark(32, 0.9).save(os.path.join(OUT, "favicon-32.png"))
    print("Icons written to", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
