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
6. Post extra "del día": saludo por fecha conmemorativa, efeméride (Wikipedia) o dato curioso.

Variables de entorno:
  ANTHROPIC_API_KEY   clave de Anthropic
  POSTIZ_API_KEY      clave pública de Postiz (Settings -> Public API)
  POSTIZ_BASE_URL     opcional, por defecto https://api.postiz.com/public/v1
  DRY_RUN=1           no publica: solo genera tarjetas y logs
  ONLY=CL,BR          opcional, limita países (HOY = solo el post del día; NONE = ninguno)
  DELETE_GROUPS=a,b   opcional, borra esos posts programados (ids de grupo) antes de generar
  POST_NOW=1          opcional, publica de inmediato (3 min) en vez de a la hora del país
"""
import os, sys, json, re, time, hashlib, datetime as dt, pathlib, urllib.parse, unicodedata
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


def norm(s):
    """minúsculas y sin acentos, para comparar nombres de medios."""
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def is_preferred(source, c):
    """True si el medio está en la lista blanca del país o en la global (config.yaml)."""
    src = norm(source)
    names = list(c.get("preferred_sources") or []) + list(CFG.get("preferred_sources_global") or [])
    for n in names:
        n = norm(n)
        if not n:
            continue
        if len(n) <= 4:  # siglas cortas (SII, BCP, TN...): solo como palabra completa
            if re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", src):
                return True
        elif n in src:
            return True
    return False


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
            source = source.strip() or fp.feed.get("title", "").strip()
            items.append({
                "key": key, "title": title.strip(), "source": source, "preferred": is_preferred(source, c),
                "link": link, "published": d.isoformat(), "summary": clean(e.get("summary", ""))[:400],
            })
    # Medios de referencia primero; si hay suficientes, los medios menores ni se muestran al modelo.
    items.sort(key=lambda x: x["published"], reverse=True)
    items.sort(key=lambda x: not x["preferred"])  # sort es estable: conserva el orden por fecha
    pref = [i for i in items if i["preferred"]]
    if len(pref) >= CFG.get("min_preferred", 3):
        items = pref
    log(f"  {code}: {len(items)} candidatos recientes ({len(pref)} de medios de referencia)")
    return items[: CFG["max_candidates"]]


# ------------------------------------------------------------------- selección
PROMPT = """Eres el editor de contenidos de DEITEL, empresa chilena (con operación en Brasil) que fabrica
torres y estructuras de acero para telecomunicaciones. Publica cada día en LinkedIn e Instagram una
noticia por país sobre economía, tributación o telecomunicaciones.

País: {name} ({code}). Idioma de redacción: {lang_name}. Fecha: {fecha}.

Candidatos (primero los de medios de referencia, marcados con ★; dentro de cada grupo, los más recientes primero):
{cands}

Tarea: elige UNA noticia. Prioridad: 1) telecomunicaciones e infraestructura (antenas, torres, 5G,
espectro, fibra, operadores, regulador), 2) economía relevante para inversión e industria, 3) tributario.
Descarta notas de farándula, deportes, política partidista, opinión, rumores y sucesos policiales
menores. REGLA DE FUENTES: elige SIEMPRE un candidato marcado con ★ (organismos oficiales y medios
económicos o generalistas de referencia del país). Solo si no hay ningún candidato ★ aceptable puedes
tomar uno sin marca, y en ese caso prefiere el medio de mayor peso. Nunca elijas un medio local pequeño
o desconocido habiendo una alternativa ★ razonable, aunque sea algo menos llamativa.
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
        star = "★ " if it.get("preferred") else ""
        lines.append(f"[{i}] {star}{it['title']} | {it['source']} | {it['published'][:16]} | {it['summary'][:200]}")
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


# ------------------------------------------------------------- post del día
def _nth_weekday(year, month, n, weekday):
    """n-ésimo día de la semana (0=lunes..6=domingo) del mes."""
    first = dt.date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    return first + dt.timedelta(days=delta + 7 * (n - 1))


def curated_dates_today():
    """Fechas de config.yaml (efemerides) que caen hoy. Formatos: 'MM-DD' o 'MM-Nsun' (N-ésimo domingo)."""
    out = []
    for e in CFG.get("efemerides") or []:
        when = str(e.get("when", ""))
        m = re.match(r"^(\d{2})-(\d{2})$", when)
        if m and int(m.group(1)) == NOW.month and int(m.group(2)) == NOW.day:
            out.append(e)
            continue
        m = re.match(r"^(\d{2})-(\d)sun$", when)
        if m and int(m.group(1)) == NOW.month and \
                _nth_weekday(NOW.year, NOW.month, int(m.group(2)), 6) == NOW.date():
            out.append(e)
    return out


def wikipedia_on_this_day():
    """Efemérides del día desde Wikipedia en español (events + holidays)."""
    mm, dd = f"{NOW.month:02d}", f"{NOW.day:02d}"
    urls = [f"https://es.wikipedia.org/api/rest_v1/feed/onthisday/all/{mm}/{dd}",
            f"https://api.wikimedia.org/feed/v1/wikipedia/es/onthisday/all/{mm}/{dd}"]
    for u in urls:
        try:
            r = requests.get(u, headers={"User-Agent": "DEITEL-news-bot/1.0 (contacto@grupodeitel.cl)"}, timeout=30)
            if r.status_code != 200:
                continue
            data = r.json()
            items = []
            for h in data.get("holidays", [])[:15]:
                items.append({"kind": "festividad", "year": None, "text": clean(h.get("text", ""))})
            evs = data.get("events", [])
            evs.sort(key=lambda x: x.get("year") or 0, reverse=True)
            for ev in evs[:40]:
                items.append({"kind": "evento", "year": ev.get("year"), "text": clean(ev.get("text", ""))})
            if items:
                return items
        except Exception as e:  # pragma: no cover
            log("  wikipedia error", e)
    return []


EXTRA_PROMPT = """Eres el editor de contenidos de DEITEL, empresa chilena (con operación en Brasil) que fabrica
torres y estructuras de acero para telecomunicaciones. Además de la noticia diaria por país, DEITEL publica
cada día UN post "del día": un saludo por una fecha conmemorativa, una efeméride ("un día como hoy") o un
dato curioso, que llame la atención y conecte con la audiencia de Chile, Brasil, Argentina, Perú y Paraguay.

Fecha de hoy: {fecha} ({weekday}).

Fechas conmemorativas de nuestra lista (tienen PRIORIDAD ABSOLUTA si hay alguna):
{curated}

Efemérides de Wikipedia para hoy (festividades y hechos históricos, con año):
{wiki}

Elige UNA opción, en este orden de prioridad:
1) SALUDO: si hoy es una fecha conmemorativa relevante (día internacional, fiesta nacional de alguno de los 5
   países, día de la profesión, fecha del sector telecomunicaciones/ingeniería), redacta un saludo cálido y
   breve, sin cursilería, que mencione a qué país o comunidad va dirigido.
2) EFEMÉRIDE: un hecho histórico de la lista, preferentemente de telecomunicaciones, ingeniería, ciencia,
   tecnología, economía o de Latinoamérica, con su año. Evita guerras, tragedias, crímenes, política partidista
   y religión. Presenta el hecho con contexto y un giro que lo vincule a la conectividad o la infraestructura.
3) DATO CURIOSO: solo si no hay nada mejor, un dato verificable y conocido sobre torres, antenas, redes,
   satélites o ingeniería estructural (indica la fuente general, p. ej. "UIT" o "Wikipedia").

Reglas: usa SOLO los hechos y años que aparecen en las listas (no inventes fechas, cifras ni nombres); escribe
en español neutro; si la fecha es propia de Brasil, escribe el post en portugués de Brasil. Sin hashtags dentro
del texto. Emojis: máximo 2 en LinkedIn y 3 en Instagram.

Responde SOLO con JSON válido, sin markdown, con estas claves:
{{
 "kind": "SALUDO" | "EFEMÉRIDE" | "DATO CURIOSO",
 "lang": "es" | "pt",
 "card_title": "<titular propio, máximo 80 caracteres, sin comillas>",
 "card_summary": "<1-2 frases, máximo 200 caracteres>",
 "linkedin": "<post de 350-700 caracteres, 2-3 párrafos cortos>",
 "instagram": "<versión de 250-500 caracteres, más directa>",
 "hashtags": "<3 hashtags específicos, separados por espacio>",
 "source": "<'Wikipedia', el nombre del organismo, o cadena vacía si es un saludo>"
}}"""


def ask_claude_extra():
    import anthropic
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    fecha = f"{NOW.day} de {MESES_ES[NOW.month - 1]} de {NOW.year}"
    cur = curated_dates_today()
    wiki = wikipedia_on_this_day()
    log(f"  fechas curadas: {len(cur)} | efemérides Wikipedia: {len(wiki)}")
    curated = "\n".join(f"- {e.get('name')} ({e.get('scope', 'general')}){': ' + e['note'] if e.get('note') else ''}"
                        for e in cur) or "- (ninguna)"
    wtxt = "\n".join(f"- [{it['kind']}{' ' + str(it['year']) if it['year'] else ''}] {it['text']}"
                     for it in wiki) or "- (sin datos; usa solo la lista curada o un dato curioso muy conocido)"
    prompt = EXTRA_PROMPT.format(fecha=fecha, weekday=dias[NOW.weekday()], curated=curated, wiki=wtxt)
    client = anthropic.Anthropic()
    for attempt in range(3):
        msg = client.messages.create(model=CFG["model"], max_tokens=1500,
                                     messages=[{"role": "user", "content": prompt}])
        txt = re.sub(r"^```(?:json)?|```$", "", msg.content[0].text.strip(), flags=re.M).strip()
        try:
            return json.loads(txt), fecha, {"curated": cur, "wikipedia": len(wiki)}
        except json.JSONDecodeError:
            log("  respuesta no JSON, reintento", attempt + 1)
            time.sleep(2)
    raise RuntimeError("Claude no devolvió JSON válido (post del día)")


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
        for path in (f"/posts/group/{group}", f"/posts/{group}"):
            r = requests.delete(f"{self.base}{path}", headers=self.h, timeout=30)
            if r.status_code < 400 or r.status_code == 404:  # 404 = ya borrado
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


def publish(pz, channels, card, texts, post_time, entry):
    """Sube la tarjeta y programa el post en todos los canales a la hora indicada (Santiago)."""
    media = pz.upload(str(card))
    hh, mm = map(int, post_time.split(":"))
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
                publish(pz, channels, card, texts, c["post_time"], entry)
                seen.add(it["key"])
        except Exception as e:
            entry.update(status="error", error=repr(e))
            log("  ERROR:", repr(e))
        daylog["countries"][code] = entry

    # ---- post del día (efeméride / saludo / dato curioso)
    extra_cfg = CFG.get("extra") or {}
    if extra_cfg.get("enabled", True) and (not ONLY or "HOY" in ONLY):
        log("== Post del día")
        entry = {"status": "skip"}
        try:
            sel, fecha, ctx = ask_claude_extra()
            if sel.get("skip"):
                entry["reason"] = sel.get("reason", "modelo descartó")
            else:
                kind = sel.get("kind", "EFEMÉRIDE")
                card = CARD_DIR / f"{TODAY}_HOY.png"
                make_card(None, kind, sel["card_title"], sel["card_summary"], sel.get("source", ""),
                          fecha, str(card), str(LOGO) if LOGO.exists() else None)
                lang = "pt" if sel.get("lang") == "pt" else "es"
                tags = CFG["hashtags"][lang] + " " + sel.get("hashtags", "")
                texts = {"linkedin": sel["linkedin"] + "\n\n" + tags.strip(),
                         "instagram": sel["instagram"] + "\n\n" + tags.strip()}
                entry.update(status="ready", selection=sel, context=ctx, card=str(card.relative_to(ROOT)))
                if not DRY:
                    t = extra_cfg.get("greeting_time", "08:45") if kind == "SALUDO" else extra_cfg.get("post_time", "16:00")
                    publish(pz, channels, card, texts, t, entry)
        except Exception as e:
            entry.update(status="error", error=repr(e))
            log("  ERROR:", repr(e))
        daylog["countries"]["HOY"] = entry

    (LOG_DIR / f"{TODAY}.json").write_text(json.dumps(daylog, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE_FILE.write_text(json.dumps({"keys": sorted(seen)[-2000:]}, indent=0), encoding="utf-8")
    log("Listo. Resumen:", {k: v["status"] for k, v in daylog["countries"].items()})
    if any(v["status"] == "error" for v in daylog["countries"].values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
