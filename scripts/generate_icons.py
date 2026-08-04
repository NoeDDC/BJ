"""One-off script that (re)generates the app icons under public/icons/.

The mark is a single geometric monogram built from two parallel bars and
one diagonal connector — exactly the letterform "skeleton" shared by both
N and Z (two parallel strokes joined by a diagonal). At 0° it reads as N,
at 90° it reads as Z; here it's rotated 45° — exactly halfway between
the two — so it evokes both Zoé and Noé without fully committing to
either.

For the larger icons, the monogram is followed by the literal letters
"oé" — so it reads as the monogram acting as the first letter, completed
into "Zoé" or "Noé" depending on which one you see in it.

Not needed at runtime — only run this manually when the mark changes:
    python scripts/generate_icons.py
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "public", "icons")
FONT_PATH = r"C:\Windows\Fonts\georgiab.ttf"

SCALE = 4  # supersample factor for crisp anti-aliased edges

INK = (28, 24, 20, 255)    # --ink
Z   = (139, 62, 47, 255)   # --z
N   = (43, 95, 107, 255)   # --n
GOLD = (201, 150, 46, 255) # --gold

GROUP_ANGLE = 45  # exactly halfway between 0° (reads as N) and 90° (reads as Z)


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
    """A bar connecting two points (x1,y1)->(x2,y2) exactly, before group rotation."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    px, py = -uy * thickness / 2, ux * thickness / 2  # perpendicular half-thickness offset
    corners = [
        (x1 + px, y1 + py),
        (x1 - px, y1 - py),
        (x2 - px, y2 - py),
        (x2 + px, y2 + py),
    ]
    return rotate(corners, GROUP_ANGLE, cx0, cy0)


def draw_monogram(d, cx, cy, glyph_h):
    """Draws the N/Z monogram centered at (cx, cy), glyph_h tall before rotation."""
    gap = glyph_h * 0.62
    thickness = glyph_h * 0.20
    left_x, right_x = cx - gap / 2, cx + gap / 2
    top_y, bottom_y = cy - glyph_h / 2, cy + glyph_h / 2

    d.polygon(bar(left_x, cy, thickness, glyph_h, cx, cy), fill=Z)
    d.polygon(bar(right_x, cy, thickness, glyph_h, cx, cy), fill=N)
    d.polygon(diagonal(left_x, top_y, right_x, bottom_y, thickness, cx, cy), fill=GOLD)


def draw_mark(size, safe_ratio):
    """Monogram alone, centered — used for the small/maskable icons."""
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s, s], fill=INK)
    draw_monogram(d, s / 2, s / 2, s * safe_ratio)
    return img.resize((size, size), Image.LANCZOS)


def draw_wordmark(size, safe_ratio):
    """Monogram followed by "oé" — reads as the monogram completed into Zoé/Noé."""
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s, s], fill=INK)

    glyph_h = s * safe_ratio * 0.85
    mono_cx = s * 0.30
    mono_cy = s * 0.5
    draw_monogram(d, mono_cx, mono_cy, glyph_h)

    font = ImageFont.truetype(FONT_PATH, int(s * safe_ratio * 0.62))
    text = "oé"
    bbox = d.textbbox((0, 0), text, font=font)
    text_cy_offset = (bbox[1] + bbox[3]) / 2
    tx = s * 0.56
    ty = s / 2 - text_cy_offset
    d.text((tx, ty), text, font=font, fill="#F2E9DC", anchor="la")

    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    draw_wordmark(512, 0.56).save(os.path.join(OUT, "icon-512.png"))
    draw_wordmark(192, 0.56).save(os.path.join(OUT, "icon-192.png"))
    draw_mark(512, 0.42).save(os.path.join(OUT, "icon-maskable-512.png"))
    draw_wordmark(180, 0.58).save(os.path.join(OUT, "apple-touch-icon.png"))
    draw_mark(32, 0.66).save(os.path.join(OUT, "favicon-32.png"))
    print("Icons written to", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
