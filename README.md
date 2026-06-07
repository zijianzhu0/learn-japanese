# jeapanese learning board

A local Japanese learning board with furigana, sentence highlighting, browser speech playback, Docker VOICEVOX playback, copy-to-clipboard, and MP4-oriented tab recording.

## Project Layout

- `index.html`: generated reading archive and article index.
- `2026-*.html`: generated article pages kept at the repo root so URLs stay simple.
- `data/articles.json`: ordered manifest of article JSON files.
- `data/articles/*.json`: source files for article content, metadata, translations, and vocabulary.
- `templates/article.html`: article page template.
- `assets/article.css`: shared article styles.
- `assets/article.js`: shared article behavior, navigation, playback, highlighting, and recording.
- `scripts/generate_site.py`: static site generator.
- `server/local_tts_server.py`: static server, VOICEVOX proxy, and MP4 conversion endpoint.
- `Dockerfile` and `docker-compose.yml`: Docker web server plus VOICEVOX engine.

## Run

```bash
docker compose up --build
```

The web container logs print the URL to open.

Open:

```text
http://127.0.0.1:8765/index.html
```

Stop:

```bash
docker compose down
```

Local Python mode also works if `ffmpeg` is installed:

```bash
python3 server/local_tts_server.py
```

## Article Workflow

Before changing article data, run the normal verification commands once so you have a clean baseline:

```bash
python3 scripts/generate_site.py
node --check assets/article.js
python3 -m py_compile server/local_tts_server.py scripts/generate_site.py
docker compose config
```

Edit existing article content in `data/articles/`, then regenerate:

```bash
python3 scripts/generate_site.py
```

To add an article:

1. Create `data/articles/YYYY-MM-DD-slug.json`.
2. Add `articles/YYYY-MM-DD-slug.json` to `data/articles.json` in display order.
3. Run `python3 scripts/generate_site.py`.
4. Re-run the verification commands from `Verify`.

Each article JSON file includes:

- `id`
- `file`
- `title`
- `date`
- `month`
- `navLabel`
- `level`
- `downloadFileName`
- `headlineHtml`
- `sourceNote`
- `paragraphs`
- `vocabularyTitle`
- `vocabulary`

The generator updates:

- root `2026-*.html` article pages
- `index.html`
- `articleNavigation` in `assets/article.js`

## Features

- Browser voice playback through `speechSynthesis`.
- Docker VOICEVOX playback through the local server:
  - `GET /api/tts/voicevox/status`
  - `POST /api/tts/voicevox`
- Voice source, browser voice, and Docker speaker preferences persist across refreshes and article pages.
- Sentence-level highlighting during playback.
- Furigana-safe article copy.
- Vertical one-page recording layout for `Render Video`.
- MP4 download when browser MP4 recording is available or server-side `ffmpeg` conversion succeeds.

## Verify

```bash
python3 scripts/generate_site.py
node --check assets/article.js
python3 -m py_compile server/local_tts_server.py scripts/generate_site.py
docker compose config
```

Optional VOICEVOX smoke test after `docker compose up --build`:

```bash
curl -s -i http://127.0.0.1:8765/api/tts/voicevox/status
curl -s -f \
  -H 'Content-Type: application/json' \
  -X POST \
  --data '{"text":"今日はテストです。","speaker":3}' \
  http://127.0.0.1:8765/api/tts/voicevox \
  -o /tmp/learn-japanese-voicevox-test.wav
```
