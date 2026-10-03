# CLAUDE.md — bot de noticias DEITEL

Contexto para Claude Code. Leer antes de tocar el repo.

## Quién y cómo trabajar
- Dueño: Marcelo Pool, DEITEL (torres autoportantes de telecomunicaciones; grupo Chile + Brasil).
  **Hablarle en español (Chile).**
- El bot es 100% automático, sin aprobación humana. Marcelo no quiere operar nada a mano:
  Claude corrige, prueba, hace push y relanza.
- **Antes de publicar de verdad o borrar posts en Postiz, avisarle qué se va a hacer.**
- Repo público `marcelopool-netizen/deitel-noticias`, rama `main`. Clon local en
  `C:\Users\ACER\code\deitel-noticias` (fuera de OneDrive a propósito).

## Qué hace (bot/bot.py)
1. **Modo normal**: cada día, 1 noticia por país (CL, BR, AR, PE, PY) de economía, tributación y
   sobre todo telecom, en el idioma del país (pt para BR) + 1 "post del día" (saludo por fecha
   conmemorativa de `efemerides`, efeméride de Wikipedia o dato curioso).
2. Recolecta noticias de las últimas 36 h (Google News RSS + `feeds` de `bot/config.yaml`).
   Lista blanca de medios: `preferred_sources` por país + `preferred_sources_global`; si hay
   ≥ `min_preferred` (3) candidatos de referencia, al modelo solo se le muestran esos.
3. Claude (modelo en `config.yaml > model`, SDK `anthropic<1`) elige y redacta LinkedIn + Instagram.
4. `bot/make_card.py` genera la tarjeta PNG 1080×1080 (logo Deitel Brasil desde `bot/logo.b64` →
   `bot/logo.png`, naranja `#FC4500`, Poppins descargada a `bot/fonts/`).
5. Sube la imagen y programa en Postiz (API pública, base `https://api.postiz.com/public/v1`):
   `POST /upload`, `POST /posts`, `DELETE /posts/group/{group}`, `GET /integrations`.
6. Guarda `logs/YYYY-MM-DD.json`, `cards/YYYY-MM-DD/`, `state/published.json` (noticias ya usadas)
   y el workflow hace commit.
7. **Idempotencia**: lee el log de hoy y omite lo que ya está `scheduled`, salvo `FORCE=1`.

## Campaña Futurecom 2026 (activa 2026-10-03 a 2026-10-08)
- `config.yaml > campaign`: con la fecha en rango NO se publican noticias ni post del día; solo los
  posts fijos `campaign.posts` (FC1..FC7) cuya `date` es hoy, a su `time` (hora Santiago).
  Textos fijos en `es` y `pt`; no usan Claude.
- Feria: Futurecom 2026, 6 al 8 de octubre, São Paulo Expo, stand/estande **I023**.
- Cada post tiene `photo` (`bot/assets/futurecom/*.jpg`, fotos reales) y `focus`; se genera con
  `make_photo_card` (foto arriba, bloque naranja con titular, pie oscuro con Fecha/Lugar/Stand).
  `make_event_card` (torre dibujada) es solo respaldo: **a Marcelo NO le gusta la torre dibujada, no usarla.**
- Idioma por cuenta: `channels[].lang` (es por defecto; Instagram "Deitel Brasil" = pt).
  El log registra por post e idioma: `FC1-es`, `FC1-pt` (así una cuenta conectada después recibe
  su post en el siguiente run sin duplicar las demás).
- Logo del evento: si existe `bot/futurecom_logo.png` (archivo OFICIAL del kit de expositor) va en el pie.
  **Nunca dibujar ni descargar el logo de Futurecom.**
- Desde el 09/10 vuelve solo a las noticias (la campaña se apaga sola por fecha).
- Estado al 03/10: FC1 quedó programado para las 17:00 en las 3 cuentas en español.

## Canales Postiz (config.yaml > channels; match por plataforma + nombre sin espacios/puntos/guiones)
| Cuenta | Plataforma | Integration id | lang |
|---|---|---|---|
| Deitel SPA | instagram | cmu7tv1l003l4lb0ydst38wb3 | es |
| Grupodeitel | linkedin-page | cmu7tmjgs08i5mo0y3lp0eimk | es |
| Marcelo Pool Skiadaressis | linkedin | cmu7sq33e03belb0yzk9botks | es |
| Deitel Brasil | instagram | pendiente de conectar en Postiz (el bot la detecta sola por nombre) | pt |

Sitios: **deitel.cl** (Chile) y **deitel.com.br** (Brasil). **Nunca `grupodeitel.cl` en las tarjetas.**

## Workflow (.github/workflows/daily.yml)
- Cron 10:00 y 12:30 UTC (GitHub atrasa hasta ~3 h; el segundo es respaldo, la idempotencia evita duplicar).
- Secrets: `ANTHROPIC_API_KEY`, `POSTIZ_API_KEY`.
- Inputs de "Run workflow": `dry_run` (1 = no publica), `only` (`CL,BR`, `HOY`, `FC`, `FC1`… o `NONE`),
  `delete_groups` (ids de GRUPO de Postiz, separados por coma), `post_now`, `force`.
- Lanzar: `gh workflow run daily.yml -f only=FC1 -f dry_run=1`
  (en este PC `gh` aún no está instalado; instalar con `winget install GitHub.cli` y `gh auth login`).
- El paso final hace `git add cards logs state` + commit + push con el usuario `deitel-noticias-bot`.

## Cómo probar
- **Siempre en local primero**: `DRY_RUN=1 python bot/bot.py` (genera tarjetas y log sin publicar).
  Mirar las tarjetas PNG antes de hacer push.
- Simular otra fecha de campaña: parchear `bot.TODAY` y `bot.CARD_DIR` desde un script de prueba
  (y `bot.NOW` si importa la hora).
- **No subir a git `cards/` ni `logs/` de pruebas locales**: esos los commitea el workflow.
  Antes de commitear, revisar `git status` y descartar los cambios locales en `cards/`, `logs/`, `state/`.

## Problemas conocidos
- `credit balance is too low` en todo: se acabaron los créditos de Anthropic
  (console.anthropic.com → Plans & Billing). No es un bug.
- `delete_groups` necesita el **id de grupo** (campo `group` de los posts en Postiz), no el `postId`.
  Con `postId` Postiz responde 404 y hoy el bot lo cuenta como borrado. `delete_group` no tiene
  try/except: un timeout tumba el run antes de escribir el log.
  Además, `POST /posts` solo devuelve `[{postId, integration}]`, sin el grupo.
- Los títulos en logs a veces conservan el sufijo " - Medio" (Google News).

## Pendientes
1. ~~Crear CLAUDE.md~~ (hecho).
2. Arreglar `delete_group` (try/except, timeout más largo, no contar 404 como borrado) y guardar el
   id de grupo en los logs al programar.
3. Cuando Marcelo conecte Instagram "Deitel Brasil" en Postiz: verificar con dry run que el bot lo
   encuentra y que recibe los posts en portugués.
4. Si Marcelo deja el logo oficial de Futurecom: guardarlo como `bot/futurecom_logo.png` y revisar
   cómo se ve en las tarjetas.
