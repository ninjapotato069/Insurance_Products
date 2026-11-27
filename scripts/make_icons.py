#!/usr/bin/env python3
"""Draw the app icons (trophy on the navy season band) into icons/.

icon-192/512: rounded square on transparent corners; maskable-512: full bleed, trophy inside the 80% safe zone;
apple-touch-icon: full square (iOS rounds it). Drawn at 4x and downsampled for clean edges.
"""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "icons"
NAVY_TOP, NAVY_BOT = (27, 45, 116), (13, 26, 69)
GOLD, SAFFRON = (245, 179, 36), (232, 89, 12)


def vgrad(n, top, bot):
    """Vertical gradient from top colour to bottom colour."""
    m = Image.linear_gradient("L").resize((n, n))
    return Image.composite(Image.new("RGB", (n, n), bot), Image.new("RGB", (n, n), top), m)


def background(n):
    """Navy gradient with a saffron glow in the top-right corner."""
    im = vgrad(n, NAVY_TOP, NAVY_BOT)
    glow = Image.new("L", (n, n), 0)
    ImageDraw.Draw(glow).ellipse([n * 0.45, -n * 0.55, n * 1.55, n * 0.55], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(n * 0.16))
    return Image.composite(Image.new("RGB", (n, n), SAFFRON), im, glow)


def trophy_mask(n, scale):
    """Trophy silhouette in an n-pixel square; scale is the share of the square the glyph spans."""
    m = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(m)
    s = n * scale / 100.0 / 100.0   # pixels per glyph unit (the glyph is drawn on a 100-unit grid)
    ox = oy = (n - 100 * s) / 2

    def P(x, y):
        return (ox + x * s, oy + y * s)

    def box(x0, y0, x1, y1):
        return [P(x0, y0), P(x1, y1)]

    d.rectangle(box(28, 12, 72, 26), fill=255)                 # cup rim
    d.chord(box(28, -8, 72, 58), 0, 180, fill=255)             # cup bowl
    w = max(1, round(7 * s))
    d.arc(box(15, 16, 41, 44), 90, 270, fill=255, width=w)     # left handle
    d.arc(box(59, 16, 85, 44), 270, 90, fill=255, width=w)     # right handle
    d.rectangle(box(45, 56, 55, 72), fill=255)                 # stem
    d.rounded_rectangle(box(32, 71, 68, 80), radius=2 * s, fill=255)
    d.rounded_rectangle(box(26, 80, 74, 90), radius=3 * s, fill=255)
    # star cut out of the bowl
    cx, cy, r1, r2 = 50, 30, 11, 4.6
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = r1 if i % 2 == 0 else r2
        pts.append(P(cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=0)
    return m


def glyph(n, scale):
    mask = trophy_mask(n, scale)
    grad = vgrad(n, GOLD, SAFFRON)
    shadow = mask.filter(ImageFilter.GaussianBlur(n * 0.02))
    return grad, mask, shadow


def render(size, scale, rounded):
    n = size * 4
    bg = background(n).convert("RGBA")
    grad, mask, shadow = glyph(n, scale)
    off = Image.new("L", (n, n), 0)
    off.paste(shadow, (0, round(n * 0.015)))
    bg = Image.composite(Image.new("RGBA", (n, n), (0, 0, 0, 255)), bg, off.point(lambda v: v * 45 // 100))
    bg = Image.composite(grad.convert("RGBA"), bg, mask)
    if rounded:
        corner = Image.new("L", (n, n), 0)
        ImageDraw.Draw(corner).rounded_rectangle([0, 0, n - 1, n - 1], radius=round(n * 0.22), fill=255)
        bg.putalpha(corner)
    return bg.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(exist_ok=True)
    render(192, 64, True).save(OUT / "icon-192.png")
    render(512, 64, True).save(OUT / "icon-512.png")
    render(512, 50, False).save(OUT / "maskable-512.png")
    render(180, 60, False).convert("RGB").save(OUT / "apple-touch-icon.png")
    print("icons written to", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
