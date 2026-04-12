"""
Generate FritzCall plugin icons.

Produces:
  src/FritzCall/icon.png     (256x256  - plugin-menu icon)
  src/FritzCall/plugin.png   (same image, alias used by Enigma2)
  src/FritzCall/res/qr_buymeacoffee.png  (simple QR-style placeholder)

Run:  C:\\Python312\\python.exe scripts/generate_icons.py
"""
import math
import os
import struct
import zlib

# ---------------------------------------------------------------------------
# Minimal PNG writer  (no dependency needed – Pillow is used below)
# ---------------------------------------------------------------------------
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC_DIR = os.path.join(BASE, "src", "FritzCall")
RES_DIR = os.path.join(SRC_DIR, "res")
os.makedirs(RES_DIR, exist_ok=True)


def _phone_poly(cx, cy, r):
    """Return polygon points for a stylised handset."""
    # Earpiece oval  (top-right)
    # Mouthpiece oval (bottom-left)
    # Body arc connecting them
    pts = []
    # Handset body as a thick tilted rectangle + two ovals approximated by
    # a polygon.  We build it as two rounded caps + a rotated rectangle.
    angle = -40  # degrees, tilt of the handset
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def rot(x, y):
        return (cx + x * cos_a - y * sin_a,
                cy + x * sin_a + y * cos_a)

    w = r * 0.28   # half-width of the handle
    h = r * 0.72   # half-height of the body

    # Rectangular shaft
    corners = [rot(-w, -h), rot(w, -h), rot(w, h), rot(-w, h)]
    pts.extend(corners)

    # Top cap  (ear piece)
    cap_r = r * 0.42
    for i in range(12):
        a = math.radians(i * 30)
        ox, oy = 0, -h
        pts.append(rot(ox + cap_r * math.cos(a), oy + cap_r * math.sin(a)))

    # Bottom cap  (mouth piece)
    for i in range(12):
        a = math.radians(i * 30)
        ox, oy = 0, h
        pts.append(rot(ox + cap_r * math.cos(a), oy + cap_r * math.sin(a)))

    return pts


def make_plugin_icon(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background – rounded rectangle, AVM-inspired deep red
    bg_color = (196, 30, 58)       # AVM red
    shadow_color = (100, 10, 25)

    margin = size // 12
    r_corner = size // 8

    # Shadow
    draw.rounded_rectangle(
        [margin + 4, margin + 4, size - margin + 4, size - margin + 4],
        radius=r_corner, fill=(*shadow_color, 180)
    )
    # Background
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=r_corner, fill=bg_color
    )

    # White phone handset (convex hull of two discs + body)
    cx, cy = size // 2, size // 2
    phone_r = size * 0.30

    # Draw as two fat ellipses + thick line (simpler & robust across PIL versions)
    lw = int(size * 0.11)
    ear_offset = size * 0.22
    mouth_offset = -size * 0.22
    tilt = -40
    tr = math.radians(tilt)

    def tpt(dx, dy):
        return (cx + dx * math.cos(tr) - dy * math.sin(tr),
                cy + dx * math.sin(tr) + dy * math.cos(tr))

    # Earpiece disc
    er = int(size * 0.13)
    ex, ey = tpt(0, -ear_offset)
    draw.ellipse([ex - er, ey - er, ex + er, ey + er], fill="white")

    # Mouthpiece disc
    mx, my = tpt(0, -mouth_offset)
    draw.ellipse([mx - er, my - er, mx + er, my + er], fill="white")

    # Body connecting line
    draw.line([(ex, ey), (mx, my)], fill="white", width=lw)

    # "FC" text below the handset
    font_size = size // 7
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    text = "FritzCall"
    # Use textbbox if available (Pillow ≥ 8), else textsize
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(text, font=font)

    tx = (size - tw) // 2
    ty = size - margin - th - size // 20
    draw.text((tx + 1, ty + 1), text, font=font, fill=(*shadow_color, 200))
    draw.text((tx, ty), text, font=font, fill="white")

    return img


def make_qr_placeholder(size=240):
    """Generate a simple branded placeholder for the BuyMeACoffee QR image."""
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)

    # Border
    bw = size // 16
    draw.rectangle([0, 0, size - 1, size - 1], outline=(196, 30, 58), width=bw)

    # Inner grid 7x7 like a QR finder pattern
    cell = (size - 2 * bw) // 9
    off = bw + cell

    def finder(ox, oy):
        draw.rectangle([ox, oy, ox + 7 * cell - 1, oy + 7 * cell - 1],
                       outline="black", width=cell)
        inner = cell * 2
        draw.rectangle([ox + inner, oy + inner,
                        ox + 7 * cell - 1 - inner, oy + 7 * cell - 1 - inner],
                       fill="black")

    finder(off, off)
    finder(size - off - 7 * cell, off)
    finder(off, size - off - 7 * cell)

    # Centre text
    try:
        f = ImageFont.truetype("arialbd.ttf", size // 9)
    except Exception:
        try:
            f = ImageFont.truetype("DejaVuSans-Bold.ttf", size // 9)
        except Exception:
            f = ImageFont.load_default()

    lines = ["Buy me", "a coffee", ":)"]
    y = size // 2 - len(lines) * (size // 9) // 2
    for line in lines:
        try:
            bb = draw.textbbox((0, 0), line, font=f)
            tw = bb[2] - bb[0]
        except AttributeError:
            tw, _ = draw.textsize(line, font=f)
        draw.text(((size - tw) // 2, y), line, font=f, fill=(196, 30, 58))
        y += size // 9 + 2

    return img


if __name__ == "__main__":
    icon = make_plugin_icon(256)
    icon_path = os.path.join(SRC_DIR, "icon.png")
    plugin_path = os.path.join(SRC_DIR, "plugin.png")
    icon.save(icon_path, "PNG")
    icon.save(plugin_path, "PNG")
    print("Saved", icon_path)
    print("Saved", plugin_path)

    qr = make_qr_placeholder(240)
    qr_path = os.path.join(RES_DIR, "qr_buymeacoffee.png")
    qr.save(qr_path, "PNG")
    print("Saved", qr_path)
