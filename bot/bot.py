#!/usr/bin/env python3
"""
Bot diario de noticias DEITEL
-----------------------------
1. Recolecta noticias recientes por país (Google News RSS + feeds oficiales).
2. Pide a Claude que elija la más relevante (economía / tributario / telecom,
   con prioridad telecomunicaciones) y redacte los textos.
3. Genera la tarjeta PNG con marca DEITEL.
4. Sube la imagen a Postiz y programa el post en cada canal configurado.
5. Guarda registro en logs/ y evita repetir noticias (state/published.json).

Variables de entorno:
  ANTHROPIC_API_KEY   clave de Anthropic
  POSTIZ_API_KEY      clave pública de Postiz (Settings -> Public API)
  POSTIZ_BASE_URL     opcional, por defecto https://api.postiz.com/public/v1
  DRY_RUN=1           no publica: solo genera tarjetas y logs
  ONLY=CL,BR          opcional, limita países
  DELETE_GROUPS=a,b   opcional, borra esos posts programados (ids de grupo) antes de generar
  POST_NOW=1          opcional, publica de inmediato (3 min) en vez de a la hora del país
"""
import os, sys, json, re, time, hashlib, datetime as dt, pathlib, urllib.parse
import requests, yaml, feedparser
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from make_card import make_card  # noqa: E402

CFG = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
TZ = ZoneInfo(CFG["timezone"])
NOW = dt.datetime.now(TZ)
TODAY = NOW.strftime("%Y-%m-%d")
DRY = os.environ.get("DRY_RUN") == "1"
ONLY = [c for c in os.environ.get("ONLY", "").split(",") if c]

STATE_FILE = ROOT / "state" / "published.json"
LOG_DIR = ROOT / "logs"
CARD_DIR = ROOT / "cards" / TODAY
LOGO = HERE / "logo.png"

MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
            "agosto", "setembro", "outubro", "novembro", "dezembro"]


def log(*a):
    print(f"[{dt.datetime.now(TZ):%H:%M:%S}]", *a, flush=True)


# ----------------------------------------------------------------- recolección
def gnews_url(q, c):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
            + f"&hl={c['hl']}&gl={c['gl']}&ceid={urllib.parse.quote(c['ceid'])}")


def parse_date(entry):
    for k in ("published_parsed", "updated_parsed"):
        t = entry.get(k)
        if t:
            return dt.datetime(*t[:6], tzinfo=dt.timezone.utc).astimezone(TZ)
    return None


def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def collect(code, c, seen):
    urls = [gnews_url(q, c) for q in c["queries"]] + list(c.get("feeds", []))
    cutoff = NOW - dt.timedelta(hours=CFG["window_hours"])
    items, keys = [], set()
    for u in urls:
        try:
            fp = feedparser.parse(u, request_headers={"User-Agent": "Mozilla/5.0 DEITEL-news-bot"})
        except Exception as e:  # pragma: no cover
            log("  feed error", u, e)
            continue
        for e in fp.entries:
            d = parse_date(e)
            if not d or d < cutoff:
                continue
            title = clean(e.get("title", ""))
            link = e.get("link", "")
            key = hashlib.sha1(re.sub(r"\W+", "", title.lower())[:80].encode()).hexdigest()
            if not title or key in keys or key in seen:
                continue
            keys.add(key)
            source = ""
            if "source" in e and getattr(e.source, "title", None):
                source = e.source.title
            elif " - " in title:  # Google News agrega " - Fuente" al final
                title, source = title.rsplit(" - ", 1)
            items.append({
                "key": key, "title": title.strip(), "source": source.strip() or fp.feed.get("title", "").strip(),
                "link": link, "published": d.isoformat(), "summary": clean(e.get("summary", ""))[:400],
            })
    items.sort(key=lambda x: x["published"], reverse=True)
    log(f"  {code}: {len(items)} candidatos recientes")
    return items[: CFG["max_candidates"]]


# ------------------------------------------------------------------- selección
PROMPT = """Eres el editor de contenidos de DEITEL, empresa chilena (con operación en Brasil) que fabrica
torres y estructuras de acero para telecomunicaciones. Publica cada día en LinkedIn e Instagram una
noticia por país sobre economía, tributación o telecomunicaciones.

País: {name} ({code}). Idioma de redacción: {lang_name}. Fecha: {fecha}.

Candidatos (los más recientes primero):
{cands}

Tarea: elige UNA noticia. Prioridad: 1) telecomunicaciones e infraestructura (antenas, torres, 5G,
espectro, fibra, operadores, regulador), 2) economía relevante para inversión e industria, 3) tributario.
Descarta notas de farándula, deportes, política partidista, opinión, rumores y sucesos policiales
menores. Entre dos noticias similares, prefiere SIEMPRE la de fuente de mayor peso: organismos
oficiales (reguladores, ministerios, bancos centrales, servicios de impuestos) y medios económicos o
generalistas de referencia del país (por ejemplo Diario Financiero, El Mercurio, La Tercera, Valor
Econômico, Folha, Estadão, Agência Brasil, Teletime, Telesíntese, La Nación, Clarín, Ámbito, Infobae,
iProfesional, Gestión, El Comercio, La República, Última Hora, ABC Color, La Nación PY, 5Días). Evita
medios locales pequeños o desconocidos salvo que sean la única cobertura de un hecho importante.
Si ninguna sirve, devuelve {{"skip": true, "reason": "..."}}.

Reglas de redacción: no expandas siglas de organismos salvo que estés seguro de su significado
(escribe solo la sigla, por ejemplo "ARCA", "SII", "SUNAT", "DNIT", "Anatel"); no inventes cifras ni
nombres; escribe con tus propias palabras. La línea final de cita es "Fuente: <medio>" en español y
"Fonte: <medio>" en portugués.

Responde SOLO con JSON válido, sin markdown, con estas claves:
{{
 "index": <número del candidato elegido>,
 "category": "ECONOMÍA" | "TRIBUTARIO" | "TELECOM"   (en portugués: "ECONOMIA" | "TRIBUTÁRIO" | "TELECOM"),
 "card_title": "<titular propio, máximo 90 caracteres, sin comillas>",
 "card_summary": "<resumen propio de 1-2 frases, máximo 220 caracteres>",
 "linkedin": "<post de 500-900 caracteres, tono profesional y cercano, 2-4 párrafos cortos, contexto y por qué importa para la industria de infraestructura telecom. Sin hashtags. Sin emojis excesivos (máximo 2). Termina citando la fuente ('Fuente: <medio>' o, en portugués, 'Fonte: <medio>')>",
 "instagram": "<versión de 300-600 caracteres para Instagram, más directa, puede llevar 1-3 emojis, termina con la misma línea de fuente>",
 "hashtags": "<3 hashtags adicionales específicos de la noticia, separados por espacio>"
}}
Escribe con tus propias palabras (no copies párrafos de la nota) y no inventes cifras que no estén en los candidatos."""


def ask_claude(code, c, cands):
    import anthropic
    lang_name = "portugués de Brasil" if c["lang"] == "pt" else "español neutro (Chile)"
    meses = MESES_PT if c["lang"] == "pt" else MESES_ES
    fecha = f"{NOW.day} de {meses[NOW.month - 1]} de {NOW.year}"
    lines = []
    for i, it in enumerate(cands):
        lines.append(f"[{i}] {it['title']} | {it['source']} | {it['published'][:16]} | {it['summary'][:200]}")
    prompt = PROMPT.format(name=c["name"], code=code, lang_name=lang_name, fecha=fecha, cands="\n".join(lines))
    client = anthropic.Anthropic()
    for attempt in range(3):
        msg = client.messages.create(model=CFG["model"], max_tokens=1500,
                                     messages=[{"role": "user", "content": prompt}])
        txt = msg.content[0].text.strip()
        txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
        try:
            return json.loads(txt), fecha
        except json.JSONDecodeError:
            log("  respuesta no JSON, reintento", attempt + 1)
            time.sleep(2)
    raise RuntimeError("Claude no devolvió JSON válido")


# --------------------------------------------------------------------- Postiz
class Postiz:
    def __init__(self):
        self.base = os.environ.get("POSTIZ_BASE_URL", "https://api.postiz.com/public/v1").rstrip("/")
        self.h = {"Authorization": os.environ["POSTIZ_API_KEY"]}

    def integrations(self):
        r = requests.get(f"{self.base}/integrations", headers=self.h, timeout=30)
        r.raise_for_status()
        return r.json()

    def upload(self, path):
        with open(path, "rb") as f:
            r = requests.post(f"{self.base}/upload", headers=self.h,
                              files={"file": (os.path.basename(path), f, "image/png")}, timeout=120)
        r.raise_for_status()
        return r.json()

    def delete_group(self, group):
        """Elimina un post programado (por id de grupo o de post) en Postiz."""
        for path in (f"/posts/{group}",):
            r = requests.delete(f"{self.base}{path}", headers=self.h, timeout=30)
            if r.status_code < 400:
                return True
        log(f"  AVISO: no se pudo borrar {group}: {r.status_code} {r.text[:200]}")
        return False

    def create_post(self, integration_id, platform, content, media, when_utc):
        settings = {"__type": platform}
        if platform.startswith("instagram"):
            settings["post_type"] = "post"
        body = {
            "type": "schedule",
            "date": when_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "shortLink": False,
            "tags": [],
            "posts": [{
                "integration": {"id": integration_id},
                "value": [{"content": content, "image": [{"id": media["id"], "path": media["path"]}]}],
                "settings": settings,
            }],
        }
        r = requests.post(f"{self.base}/posts", headers={**self.h, "Content-Type": "application/json"},
                          json=body, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Postiz {r.status_code}: {r.text[:500]}")
        return r.json()


def _platform_of(i):
    for k in ("identifier", "providerIdentifier", "platform", "provider", "type"):
        if i.get(k):
            return str(i[k]).lower()
    return ""


def resolve_channels(pz):
    ints = pz.integrations()
    if isinstance(ints, dict):  # algunas versiones envuelven la lista
        ints = ints.get("integrations") or ints.get("data") or []
    out = []
    for ch in CFG["channels"]:
        m = [i for i in ints if _platform_of(i) == ch["platform"].lower()
             and ch["name"].lower() in (i.get("name") or "").lower()]
        if not m:
            log(f"  AVISO: canal no encontrado en Postiz: {ch}")
            continue
        out.append({"id": m[0]["id"], "platform": ch["platform"], "name": m[0]["name"]})
    if not out:
        raise RuntimeError("Ningún canal de Postiz coincide con config.yaml. Respuesta de /integrations: "
                           + json.dumps(ints, ensure_ascii=False)[:800])
    return out


# ----------------------------------------------------------------------- main
def main():
    seen = set(json.loads(STATE_FILE.read_text()).get("keys", [])) if STATE_FILE.exists() else set()
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    STATE_FILE.parent.mkdir(exist_ok=True)
    daylog = {"date": TODAY, "run_at": NOW.isoformat(), "dry_run": DRY, "countries": {}}
    prev_log = LOG_DIR / f"{TODAY}.json"
    if ONLY and prev_log.exists():  # corrida parcial: conservar lo ya registrado hoy
        try:
            daylog["countries"] = json.loads(prev_log.read_text(encoding="utf-8")).get("countries", {})
        except Exception:
            pass

    pz = channels = None
    if not DRY:
        pz = Postiz()
        try:
            channels = resolve_channels(pz)
            log("Canales:", [c["name"] for c in channels])
        except Exception as e:
            log("ERROR resolviendo canales:", repr(e))
            daylog["error"] = repr(e)
            (LOG_DIR / f"{TODAY}.json").write_text(json.dumps(daylog, ensure_ascii=False, indent=2), encoding="utf-8")
            sys.exit(1)

    groups = [g for g in os.environ.get("DELETE_GROUPS", "").replace("\n", ",").split(",") if g.strip()]
    if groups and not DRY:
        log(f"Borrando {len(groups)} posts programados en Postiz...")
        daylog["deleted"] = [g for g in groups if pz.delete_group(g.strip())]

    for code, c in CFG["countries"].items():
        if ONLY and code not in ONLY:
            continue
        log(f"== {c['name']}")
        entry = {"status": "skip"}
        try:
            cands = collect(code, c, seen)
            if not cands:
                entry["reason"] = "sin candidatos recientes"
                daylog["countries"][code] = entry
                continue
            sel, fecha = ask_claude(code, c, cands)
            if sel.get("skip"):
                entry["reason"] = sel.get("reason", "modelo descartó")
                daylog["countries"][code] = entry
                continue
            it = cands[int(sel["index"])]
            card = CARD_DIR / f"{TODAY}_{code}.png"
            make_card(code, sel["category"], sel["card_title"], sel["card_summary"],
                      it["source"] or "Prensa", fecha, str(card), str(LOGO) if LOGO.exists() else None)
            tags = CFG["hashtags"][c["lang"]] + " " + sel.get("hashtags", "")
            texts = {
                "linkedin": sel["linkedin"] + "\n\n" + tags.strip(),
                "instagram": sel["instagram"] + "\n\n" + tags.strip(),
            }
            entry.update(status="ready", news=it, selection=sel, card=str(card.relative_to(ROOT)))

            if not DRY:
                media = pz.upload(str(card))
                hh, mm = map(int, c["post_time"].split(":"))
                when = NOW.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if os.environ.get("POST_NOW") == "1" or when < NOW + dt.timedelta(minutes=5):
                    when = NOW + dt.timedelta(minutes=3)
                when_utc = when.astimezone(dt.timezone.utc)
                entry["posts"] = []
                for ch in channels:
                    content = texts["instagram" if ch["platform"].startswith("instagram") else "linkedin"]
                    res = pz.create_post(ch["id"], ch["platform"], content, media, when_utc)
                    entry["posts"].append({"channel": ch["name"], "scheduled_for": when.isoformat(), "result": res})
                    log(f"  programado en {ch['name']} para {when:%H:%M}")
                if not entry["posts"]:
                    raise RuntimeError("sin canales: no se programó ningún post")
                entry["status"] = "scheduled"
                seen.add(it["key"])
        except Exception as e:
            entry.update(status="error", error=repr(e))
            log("  ERROR:", repr(e))
        daylog["countries"][code] = entry

    (LOG_DIR / f"{TODAY}.json").write_text(json.dumps(daylog, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE_FILE.write_text(json.dumps({"keys": sorted(seen)[-2000:]}, indent=0), encoding="utf-8")
    log("Listo. Resumen:", {k: v["status"] for k, v in daylog["countries"].items()})
    if any(v["status"] == "error" for v in daylog["countries"].values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
