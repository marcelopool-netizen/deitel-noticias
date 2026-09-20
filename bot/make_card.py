#!/usr/bin/env python3
"""Genera la tarjeta de noticia con marca DEITEL (1080x1080 PNG).

Uso:
  python3 make_card.py --country CL --category TELECOM \
      --title "Titular de la noticia" --summary "Resumen corto..." \
      --source "Diario Financiero" --date "20 sep 2026" --out card.png [--logo logo.png]
"""
import argparse, textwrap
from PIL import Image, ImageDraw, ImageFont

W = H = 1080
BG = (255, 255, 255)
BG_BOTTOM = (244, 245, 247)
ORANGE = (252, 69, 0)
INK = (19, 23, 25)
GREY = (90, 98, 108)
LINE = (215, 220, 226)
WHITE = (255, 255, 255)

import os
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts") + os.sep
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/"


def font(name, size):
    path = FONT_DIR + name
    if not os.path.exists(path):  # descarga Poppins (licencia OFL) si no está en bot/fonts
        import urllib.request
        os.makedirs(FONT_DIR, exist_ok=True)
        urllib.request.urlretrieve(FONT_URL + name, path)
    return ImageFont.truetype(path, size)

COUNTRIES = {
    "CL": ("CHILE", "chile"),
    "BR": ("BRASIL", "brasil"),
    "AR": ("ARGENTINA", "argentina"),
    "PE": ("PERÚ", "peru"),
    "PY": ("PARAGUAY", "paraguay"),
}

CATEGORY_COLORS = {
    "ECONOMÍA": (19, 23, 25),
    "ECONOMIA": (19, 23, 25),
    "TRIBUTARIO": (90, 98, 108),
    "TRIBUTÁRIO": (90, 98, 108),
    "TELECOM": ORANGE,
    "TELECOMUNICACIONES": ORANGE,
    "TELECOMUNICAÇÕES": ORANGE,
}


def draw_flag(code, w=96, h=64):
    """Banderas simplificadas (sin escudos) dibujadas con PIL."""
    im = Image.new("RGB", (w, h), WHITE)
    d = ImageDraw.Draw(im)
    if code == "CL":
        d.rectangle([0, h // 2, w, h], fill=(213, 43, 30))
        d.rectangle([0, 0, w // 3, h // 2], fill=(0, 57, 166))
        cx, cy, r = w // 6, h // 4, h // 7
        pts = []
        import math
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.45
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        d.polygon(pts, fill=WHITE)
    elif code == "BR":
        d.rectangle([0, 0, w, h], fill=(0, 155, 58))
        d.polygon([(w / 2, 6), (w - 8, h / 2), (w / 2, h - 6), (8, h / 2)], fill=(254, 223, 0))
        r = h // 4
        d.ellipse([w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r], fill=(0, 39, 118))
    elif code == "AR":
        d.rectangle([0, 0, w, h // 3], fill=(116, 172, 223))
        d.rectangle([0, 2 * h // 3, w, h], fill=(116, 172, 223))
        r = h // 8
        d.ellipse([w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r], fill=(246, 180, 14))
    elif code == "PE":
        d.rectangle([0, 0, w // 3, h], fill=(217, 16, 35))
        d.rectangle([2 * w // 3, 0, w, h], fill=(217, 16, 35))
    elif code == "PY":
        d.rectangle([0, 0, w, h // 3], fill=(213, 43, 30))
        d.rectangle([0, 2 * h // 3, w, h], fill=(0, 56, 168))
        r = h // 9
        d.ellipse([w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r], outline=(120, 120, 120), width=2)
    # borde sutil
    d.rectangle([0, 0, w - 1, h - 1], outline=LINE, width=2)
    return im


def wrap_to_width(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_title(draw, text, max_w, max_lines, sizes=(64, 58, 52, 46, 42, 38)):
    for s in sizes:
        f = font("Poppins-Bold.ttf", s)
        lines = wrap_to_width(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines
    f = font("Poppins-Bold.ttf", sizes[-1])
    lines = wrap_to_width(draw, text, f, max_w)[:max_lines]
    lines[-1] = lines[-1].rstrip(".,;") + "…"
    return f, lines


def default_logo():
    """logo.png junto al script; si no existe, se reconstruye desde logo.b64."""
    here = os.path.dirname(os.path.abspath(__file__))
    png = os.path.join(here, "logo.png")
    b64 = os.path.join(here, "logo.b64")
    if not os.path.exists(png) and os.path.exists(b64):
        import base64
        with open(b64) as f, open(png, "wb") as out:
            out.write(base64.b64decode(f.read()))
    return png if os.path.exists(png) else None


def make_card(country, category, title, summary, source, date, out, logo=None):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # Fondo: degradado vertical sutil (blanco -> gris muy claro)
    for y in range(H):
        t = y / H
        c = tuple(int(BG[i] * (1 - t) + BG_BOTTOM[i] * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)

    logo = logo or default_logo()

    # Franja lateral naranja (identidad)
    d.rectangle([0, 0, 18, H], fill=ORANGE)

    # Cabecera: logo o wordmark
    margin = 72
    if logo:
        lg = Image.open(logo).convert("RGBA")
        lg.thumbnail((400, 140))
        im.paste(lg, (margin, 40), lg)
    else:
        d.text((margin, 56), "DEITEL", font=font("Poppins-Bold.ttf", 60), fill=INK)
        d.text((margin + 2, 126), "TORRES PARA TELECOMUNICACIONES", font=font("Poppins-Medium.ttf", 20), fill=GREY, spacing=4)

    # País + bandera, arriba a la derecha
    name = COUNTRIES[country][0]
    flag = draw_flag(country)
    fn = font("Poppins-Medium.ttf", 30)
    tw = d.textlength(name, font=fn)
    d.text((W - margin - tw, 70), name, font=fn, fill=INK)
    im.paste(flag, (W - margin - int(tw) - 96 - 20, 60))

    # Línea divisoria
    d.line([(margin, 200), (W - margin, 200)], fill=LINE, width=2)

    # Etiqueta de categoría
    cat = category.upper()
    col = CATEGORY_COLORS.get(cat, ORANGE)
    fc = font("Poppins-Bold.ttf", 26)
    cw = d.textlength(cat, font=fc)
    d.rounded_rectangle([margin, 236, margin + cw + 40, 236 + 50], radius=10, fill=col)
    d.text((margin + 20, 243), cat, font=fc, fill=WHITE)

    # Titular
    ft, tlines = fit_title(d, title, W - 2 * margin, 4)
    y = 326
    lh = int(ft.size * 1.18)
    for ln in tlines:
        d.text((margin, y), ln, font=ft, fill=INK)
        y += lh

    # Resumen
    y += 26
    fs = font("Poppins-Regular.ttf", 30)
    slines = wrap_to_width(d, summary, fs, W - 2 * margin)[:5]
    for ln in slines:
        d.text((margin, y), ln, font=fs, fill=GREY)
        y += 42

    # Pie: fuente y fecha
    d.line([(margin, H - 150), (W - margin, H - 150)], fill=LINE, width=2)
    fp = font("Poppins-Regular.ttf", 24)
    lbl = "Fonte" if country == "BR" else "Fuente"
    d.text((margin, H - 120), f"{lbl}: {source}", font=fp, fill=GREY)
    d.text((margin, H - 84), date, font=fp, fill=GREY)
    fb = font("Poppins-Medium.ttf", 24)
    tag = "grupodeitel.cl"
    d.text((W - margin - d.textlength(tag, font=fb), H - 120), tag, font=fb, fill=ORANGE)

    im.save(out, "PNG", optimize=True)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--country", required=True, choices=list(COUNTRIES))
    p.add_argument("--category", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--logo")
    a = p.parse_args()
    print(make_card(a.country, a.category, a.title, a.summary, a.source, a.date, a.out, a.logo))
