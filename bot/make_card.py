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
    # post extra del día (efemérides, saludos, datos curiosos)
    "SALUDO": ORANGE,
    "EFEMÉRIDE": (0, 92, 168),
    "EFEMERIDE": (0, 92, 168),
    "UN DÍA COMO HOY": (0, 92, 168),
    "DATO CURIOSO": (24, 128, 118),
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

    # País + bandera, arriba a la derecha (sin país: solo la fecha, para el post del día)
    fn = font("Poppins-Medium.ttf", 30)
    if country in COUNTRIES:
        name = COUNTRIES[country][0]
        flag = draw_flag(country)
        tw = d.textlength(name, font=fn)
        d.text((W - margin - tw, 70), name, font=fn, fill=INK)
        im.paste(flag, (W - margin - int(tw) - 96 - 20, 60))
    else:
        name = date.upper()
        tw = d.textlength(name, font=fn)
        d.text((W - margin - tw, 70), name, font=fn, fill=INK)
        d.rounded_rectangle([W - margin - tw, 112, W - margin, 116], radius=2, fill=ORANGE)

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
    if country not in COUNTRIES:  # post del día: la fecha ya va en la cabecera
        if source:
            d.text((margin, H - 120), f"{lbl}: {source}", font=fp, fill=GREY)
    elif source:
        d.text((margin, H - 120), f"{lbl}: {source}", font=fp, fill=GREY)
        d.text((margin, H - 84), date, font=fp, fill=GREY)
    else:
        d.text((margin, H - 120), date, font=fp, fill=GREY)
    fb = font("Poppins-Medium.ttf", 24)
    tag = {"BR": "deitel.com.br", None: "deitel.cl · deitel.com.br"}.get(country, "deitel.cl")
    d.text((W - margin - d.textlength(tag, font=fb), H - 120), tag, font=fb, fill=ORANGE)

    im.save(out, "PNG", optimize=True)
    return out


# ---------------------------------------------------------------- tarjeta de evento
NAVY = (14, 22, 34)
NAVY2 = (24, 36, 54)


def _draw_tower(d, cx, base_y, h, base_w, top_w, k):
    """Torre autoportante reticulada (ilustración propia), coordenadas ya escaladas por k."""
    top_y = base_y - h
    lx = lambda y: cx - (base_w / 2) + (base_w - top_w) / 2 * (base_y - y) / h
    rx = lambda y: 2 * cx - lx(y)
    leg = (252, 69, 0)
    brace = (255, 140, 90)
    n = 9
    ys = [base_y - h * (1 - (1 - i / n) ** 1.25) for i in range(n + 1)]
    for a, b in zip(ys, ys[1:]):
        d.line([(lx(a), a), (rx(a), a)], fill=brace, width=int(3 * k))
        d.line([(lx(a), a), (rx(b), b)], fill=brace, width=int(2 * k))
        d.line([(rx(a), a), (lx(b), b)], fill=brace, width=int(2 * k))
    d.line([(lx(base_y), base_y), (lx(top_y), top_y)], fill=leg, width=int(7 * k))
    d.line([(rx(base_y), base_y), (rx(top_y), top_y)], fill=leg, width=int(7 * k))
    # mástil, antenas de panel y microondas
    d.line([(cx, top_y), (cx, top_y - 70 * k)], fill=WHITE, width=int(4 * k))
    for side in (-1, 1):
        x = cx + side * (top_w / 2 + 14 * k)
        d.rounded_rectangle([x - 8 * k, top_y + 6 * k, x + 8 * k, top_y + 78 * k], radius=int(4 * k), fill=WHITE)
    yy = top_y + 150 * k
    r = 30 * k
    d.ellipse([lx(yy) - 2 * r - 6 * k, yy - r, lx(yy) - 6 * k, yy + r], fill=(235, 238, 242))
    d.ellipse([lx(yy) - 2 * r + 4 * k, yy - r + 10 * k, lx(yy) - 16 * k, yy + r - 10 * k], fill=(200, 206, 214))
    # ondas de radio
    for i, rr in enumerate((45, 75, 105)):
        rr *= k
        box = [cx - rr, top_y - 70 * k - rr, cx + rr, top_y - 70 * k + rr]
        col = (252, 69 + 40 * i, 40 * i)
        d.arc(box, 300, 360, fill=col, width=int(5 * k))
        d.arc(box, 180, 240, fill=col, width=int(5 * k))


def _draw_booth(d, ox, oy, s, k):
    """Stand de acero en isométrico (marco apernado con LED), ilustración propia."""
    import math
    c, sn = math.cos(math.radians(30)), math.sin(math.radians(30))
    P = lambda x, y, z: (ox + (x - y) * c * s, oy + (x + y) * sn * s - z * s)
    W_, D_, H_ = 1.6, 1.0, 1.0
    steel, led, plate = (190, 198, 210), (252, 69, 0), (60, 74, 96)
    # muros de plancha (fondo y lateral)
    d.polygon([P(0, D_, 0), P(W_, D_, 0), P(W_, D_, H_), P(0, D_, H_)], fill=plate)
    d.polygon([P(0, 0, 0), P(0, D_, 0), P(0, D_, H_), P(0, 0, H_)], fill=(48, 60, 80))
    # piso
    d.polygon([P(0, 0, 0), P(W_, 0, 0), P(W_, D_, 0), P(0, D_, 0)], fill=(90, 100, 116))
    for i in range(1, 8):
        x = W_ * i / 8
        d.line([P(x, 0, 0), P(x, D_, 0)], fill=(110, 120, 136), width=int(1 * k))
    edges = [((0,0,0),(0,0,H_)),((W_,0,0),(W_,0,H_)),((W_,D_,0),(W_,D_,H_)),((0,D_,0),(0,D_,H_)),
             ((0,0,H_),(W_,0,H_)),((W_,0,H_),(W_,D_,H_)),((W_,D_,H_),(0,D_,H_)),((0,D_,H_),(0,0,H_))]
    for a, b in edges:
        d.line([P(*a), P(*b)], fill=steel, width=int(7 * k))
    # cerchas de techo
    for i in range(1, 4):
        x = W_ * i / 4
        d.line([P(x, 0, H_), P(x, D_, H_)], fill=steel, width=int(4 * k))
        d.line([P(x - W_ / 8, 0, H_), P(x, D_, H_)], fill=steel, width=int(2 * k))
    # franjas LED en perfiles omega
    d.line([P(0, 0, H_ - 0.06), P(W_, 0, H_ - 0.06)], fill=led, width=int(6 * k))
    d.line([P(W_, 0, H_ - 0.06), P(W_, D_, H_ - 0.06)], fill=led, width=int(6 * k))
    # mini torre de exhibición dentro del stand
    _draw_tower(d, P(W_ * 0.55, D_ * 0.6, 0)[0], P(W_ * 0.55, D_ * 0.6, 0)[1], 0.85 * s, 0.30 * s, 0.06 * s, k * 0.6)


def make_event_card(title, summary, info, out, logo=None, event_logo=None, art="tower",
                    label="FUTURECOM 2026", badge="Expositor"):
    """Tarjeta ilustrada para campañas de eventos (1080x1080)."""
    k = 2  # supersampling para bordes suaves
    big = Image.new("RGB", (W * k, H * k), NAVY)
    d = ImageDraw.Draw(big)
    top_h = 640
    # fondo azul noche con degradado y retícula tipo plano
    for y in range(top_h * k):
        t = y / (top_h * k)
        c = tuple(int(NAVY[i] * (1 - t) + NAVY2[i] * t) for i in range(3))
        d.line([(0, y), (W * k, y)], fill=c)
    for x in range(0, W * k, 54 * k):
        d.line([(x, 0), (x, top_h * k)], fill=(30, 44, 64), width=k)
    for y in range(0, top_h * k, 54 * k):
        d.line([(0, y), (W * k, y)], fill=(30, 44, 64), width=k)
    if art == "booth":
        _draw_booth(d, 815 * k, 300 * k, 165 * k, k)
    else:
        _draw_tower(d, 830 * k, (top_h - 20) * k, 420 * k, 300 * k, 46 * k, k)
    # parte inferior blanca
    d.rectangle([0, top_h * k, W * k, H * k], fill=WHITE)
    im = big.resize((W, H), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    margin = 72
    # etiqueta
    fc = font("Poppins-Bold.ttf", 26)
    cw = d.textlength(label, font=fc)
    d.rounded_rectangle([margin, 70, margin + cw + 40, 120], radius=10, fill=ORANGE)
    d.text((margin + 20, 77), label, font=fc, fill=WHITE)
    # titular en blanco, columna izquierda
    ft, tlines = fit_title(d, title, 560 if art == "booth" else 600, 5, sizes=(66, 60, 54, 48, 44, 40))
    lh = int(ft.size * 1.16)
    y = 160 + max(0, (5 - len(tlines)) * lh // 3)
    for ln in tlines:
        d.text((margin, y), ln, font=ft, fill=WHITE)
        y += lh
    # franja naranja con datos del evento
    d.rectangle([0, top_h - 70, W, top_h], fill=ORANGE)
    fi = font("Poppins-Bold.ttf", 30)
    iw = d.textlength(info, font=fi)
    d.text(((W - iw) / 2, top_h - 58), info, font=fi, fill=WHITE)
    # resumen
    y = top_h + 34
    fs = font("Poppins-Regular.ttf", 32)
    for ln in wrap_to_width(d, summary, fs, W - 2 * margin)[:4]:
        d.text((margin, y), ln, font=fs, fill=GREY)
        y += 46
    # pie: logo DEITEL + logo del evento (si se entregó el archivo oficial) + web
    d.line([(margin, H - 170), (W - margin, H - 170)], fill=LINE, width=2)
    logo = logo or default_logo()
    if logo:
        lg = Image.open(logo).convert("RGBA")
        lg.thumbnail((330, 120))
        im.paste(lg, (margin, H - 150 + (120 - lg.height) // 2), lg)
    fb = font("Poppins-Medium.ttf", 24)
    if event_logo and os.path.exists(event_logo):
        el = Image.open(event_logo).convert("RGBA")
        el.thumbnail((300, 100))
        x = W - margin - el.width
        im.paste(el, (x, H - 140 + (100 - el.height) // 2), el)
        if badge:
            fbg = font("Poppins-Medium.ttf", 20)
            d.text((x, H - 162 + 4), badge.upper(), font=fbg, fill=GREY)
    else:
        tag = "deitel.cl · deitel.com.br"
        d.text((W - margin - d.textlength(tag, font=fb), H - 104), tag, font=fb, fill=ORANGE)
    im.save(out, "PNG", optimize=True)
    return out


DARK = (17, 21, 24)


def _cover(img, w, h, focus=(0.5, 0.5)):
    """Recorta la foto para llenar w x h (como CSS object-fit: cover)."""
    sc = max(w / img.width, h / img.height)
    im = img.resize((max(w, round(img.width * sc)), max(h, round(img.height * sc))), Image.LANCZOS)
    x = int((im.width - w) * focus[0])
    y = int((im.height - h) * focus[1])
    return im.crop((x, y, x + w, y + h))


def make_photo_card(title, summary, photo, out, facts, logo=None, event_logo=None,
                    kicker="FUTURECOM 2026", tag="", focus=(0.5, 0.5), web="deitel.com.br"):
    """Tarjeta con foto real arriba, bloque naranja con titular y pie oscuro con datos
    (mismo lenguaje visual que el carrusel de Instagram y el loop del estande)."""
    im = Image.new("RGB", (W, H), DARK)
    ph_h = 590
    ph = _cover(Image.open(photo).convert("RGB"), W, ph_h, focus)
    # sombra superior para que se lean logo y etiqueta
    shade = Image.new("L", (W, ph_h), 0)
    sd = ImageDraw.Draw(shade)
    for y in range(210):
        sd.line([(0, y), (W, y)], fill=int(200 * (1 - y / 210) ** 1.3))
    ph = Image.composite(Image.new("RGB", (W, ph_h), DARK), ph, shade)
    im.paste(ph, (0, 0))
    d = ImageDraw.Draw(im)
    m = 56
    # logo DEITEL en caja blanca
    logo = logo or default_logo()
    if logo:
        lg = Image.open(logo).convert("RGBA")
        lg.thumbnail((250, 78))
        d.rounded_rectangle([m, 40, m + lg.width + 32, 40 + lg.height + 24], radius=8, fill=WHITE)
        im.paste(lg, (m + 16, 52), lg)
    # etiqueta arriba a la derecha (texto espaciado)
    fk = font("Poppins-SemiBold.ttf", 22)
    def spaced(t, x_right, y, fnt, fill):
        t = " ".join(t)  # tracking
        d.text((x_right - d.textlength(t, font=fnt), y), t, font=fnt, fill=fill)
    kw = max(d.textlength(" ".join(kicker), font=fk), d.textlength(" ".join(tag), font=fk) if tag else 0)
    d.rounded_rectangle([W - m - kw - 22, 40, W - m + 18, 122 if tag else 92], radius=8, fill=DARK)
    spaced(kicker, W - m, 52, fk, WHITE)
    if tag:
        spaced(tag, W - m, 84, fk, ORANGE)
    # bloque naranja con titular
    ob_top, ob_bot = ph_h, 880
    d.rectangle([0, ob_top, W, ob_bot], fill=ORANGE)
    ft, tlines = fit_title(d, title, W - 2 * m, 2, sizes=(66, 60, 54, 48, 44))
    fs = font("Poppins-Medium.ttf", 28)
    slines = wrap_to_width(d, summary, fs, W - 2 * m)[:2]
    lh = int(ft.size * 1.12)
    block = len(tlines) * lh + 18 + len(slines) * 40
    y = ob_top + (ob_bot - ob_top - block) // 2
    for ln in tlines:
        d.text((m, y), ln, font=ft, fill=WHITE)
        y += lh
    y += 18
    for ln in slines:
        d.text((m, y), ln, font=fs, fill=DARK)
        y += 40
    # pie oscuro con datos del evento
    fl = font("Poppins-SemiBold.ttf", 18)
    fv = font("Poppins-Bold.ttf", 36)
    right = W - m
    if event_logo and os.path.exists(event_logo):
        el = Image.open(event_logo).convert("RGBA")
        el.thumbnail((230, 110))
        im.paste(el, (right - el.width, 880 + (200 - el.height) // 2), el)
        right -= el.width + 40
    cols = len(facts)
    cw = (right - m) / max(cols, 1)
    for i, (lbl, val) in enumerate(facts):
        x = m + i * cw
        d.text((x, 918), " ".join(lbl.upper()), font=fl, fill=ORANGE)
        fvv = fv
        while d.textlength(val, font=fvv) > cw - 20 and fvv.size > 24:
            fvv = font("Poppins-Bold.ttf", fvv.size - 2)
        d.text((x, 948), val, font=fvv, fill=WHITE)
    fw = font("Poppins-Medium.ttf", 20)
    d.text((m, 1030), web, font=fw, fill=(150, 156, 164))
    im.save(out, "PNG", optimize=True)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--country", default=None, choices=list(COUNTRIES), help="omitir para el post del día")
    p.add_argument("--category", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--logo")
    a = p.parse_args()
    print(make_card(a.country, a.category, a.title, a.summary, a.source, a.date, a.out, a.logo))
