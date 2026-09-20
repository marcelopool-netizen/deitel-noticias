# deitel-noticias

Bot que publica cada día en las redes de DEITEL una noticia por país (Chile, Brasil,
Argentina, Perú y Paraguay) sobre economía, tributación y, con prioridad,
telecomunicaciones. Genera texto e imagen (tarjeta con marca DEITEL) y programa
los posts en Postiz (LinkedIn Grupodeitel, Instagram Deitel SPA y LinkedIn personal).

Corre solo en **GitHub Actions** todos los días a las 08:30 (hora de Santiago).

## Cómo funciona

1. `bot/bot.py` recolecta noticias de las últimas 36 h vía Google News RSS
   (consultas por país en `bot/config.yaml`) y feeds oficiales (Subtel, Anatel, etc.).
2. Le entrega los candidatos a Claude, que elige la noticia más relevante, la
   clasifica (ECONOMÍA / TRIBUTARIO / TELECOM) y redacta el post para LinkedIn e
   Instagram, en portugués para Brasil y español para el resto.
3. `bot/make_card.py` genera la tarjeta PNG 1080×1080.
4. Sube la imagen a Postiz y programa el post en cada canal a la hora del país
   (CL 09:00, BR 10:00, AR 11:00, PE 12:00, PY 13:00, hora de Santiago).
5. Guarda la tarjeta en `cards/`, el registro en `logs/` y el listado de noticias ya
   usadas en `state/published.json` para no repetir.

## Instalación (una sola vez)

1. **Clave de Postiz**: en Postiz → Settings → *Public API* → copiar la API key.
2. **Clave de Anthropic**: en https://console.anthropic.com → API Keys → crear una.
3. En este repositorio: **Settings → Secrets and variables → Actions → New repository secret**.
   Crear dos secretos: `POSTIZ_API_KEY` y `ANTHROPIC_API_KEY`.
4. (Opcional) Reemplazar `bot/logo.png` por el logo oficial en PNG con fondo transparente.
   Si no existe, la tarjeta usa el logotipo tipográfico "DEITEL".

## Probar sin publicar

En **Actions → Noticias diarias DEITEL → Run workflow**, poner `dry_run = 1`. El bot
genera las tarjetas y el log en `cards/` y `logs/` sin publicar nada. Revisar el
resultado y luego correr con `dry_run = 0` (o esperar a la ejecución diaria).

`only = CL,BR` limita la corrida a algunos países.

## Ajustes frecuentes

- Horarios, consultas de búsqueda, feeds y hashtags: `bot/config.yaml`.
- Canales de Postiz: sección `channels` de `bot/config.yaml` (plataforma + nombre).
- Tono y criterios editoriales: variable `PROMPT` en `bot/bot.py`.
- Hora de ejecución: `cron` en `.github/workflows/daily.yml` (en UTC).
- Diseño de la tarjeta (colores, tipografía, tamaño): `bot/make_card.py`.

## Ejecutar en el PC

```
pip install -r requirements.txt
set ANTHROPIC_API_KEY=...
set POSTIZ_API_KEY=...
set DRY_RUN=1
python bot/bot.py
```
# deitel-noticias
