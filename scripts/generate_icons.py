"""One-off script that (re)generates the app icons under public/icons/.

The mark is a single geometric monogram built from two parallel bars and
one diagonal connector — exactly the letterform "skeleton" shared by both
N and Z (two parallel strokes joined by a diagonal). At 0° it reads as N,
at 90° it reads as Z; here it's rotated 45° — exactly halfway between the
two — so it evokes both Zoé and Noé without fully committing to either.

Not needed at runtime — only run this manually when the mark changes:
    python scripts/generate_icons.py
"""
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "public", "icons")

SCALE = 4  # supersample factor for crisp anti-aliased edges

INK = (28, 24, 20, 255)    # --ink
Z   = (139, 62, 47, 255)   # --z
N   = (43, 95, 107, 255)   # --n
GOLD = (201, 150, 46, 255) # --gold

GROUP_ANGLE = 45  # halfway between 0° (reads as N) and 90° (reads as Z)


def rotate(points, angle_deg, cx, cy):
    a = math.radians(angle_deg)
    cos_a, sin_a = math.cos(a), math.sin(a)
    out = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a))
    return out


def bar(cx, cy, thickness, length, cx0, cy0):
    """A vertical bar centered at (cx, cy), then rotated GROUP_ANGLE around (cx0, cy0)."""
    hw, hh = thickness / 2, length / 2
    corners = [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
    return rotate(corners, GROUP_ANGLE, cx0, cy0)


def diagonal(x1, y1, x2, y2, thickness, cx0, cy0):
    """A bar connecting two points (before group rotation), then rotated with the rest."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dx, dy))  # 0 == vertical, matches bar()'s own frame
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    hw, hh = thickness / 2, length / 2
    local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    a = math.radians(angle)
    cos_a, sin_a = math.cos(a), math.sin(a)
    corners = [(mx + px * cos_a - py * sin_a, my + px * sin_a + py * cos_a) for px, py in local]
    return rotate(corners, GROUP_ANGLE, cx0, cy0)


def draw_mark(size, safe_ratio):
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s, s], fill=INK)

    cx, cy = s / 2, s / 2
    glyph_h = s * safe_ratio       # total height of the pre-rotation "N"
    gap = glyph_h * 0.62           # horizontal distance between the two bars
    thickness = glyph_h * 0.20

    left_x, right_x = cx - gap / 2, cx + gap / 2
    top_y, bottom_y = cy - glyph_h / 2, cy + glyph_h / 2

    d.polygon(bar(left_x, cy, thickness, glyph_h, cx, cy), fill=Z)
    d.polygon(bar(right_x, cy, thickness, glyph_h, cx, cy), fill=N)
    d.polygon(diagonal(left_x, top_y, right_x, bottom_y, thickness, cx, cy), fill=GOLD)

    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    draw_mark(512, 0.60).save(os.path.join(OUT, "icon-512.png"))
    draw_mark(192, 0.60).save(os.path.join(OUT, "icon-192.png"))
    draw_mark(512, 0.42).save(os.path.join(OUT, "icon-maskable-512.png"))
    draw_mark(180, 0.62).save(os.path.join(OUT, "apple-touch-icon.png"))
    draw_mark(32, 0.66).save(os.path.join(OUT, "favicon-32.png"))
    print("Icons written to", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
