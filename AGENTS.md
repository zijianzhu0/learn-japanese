# AGENTS.md

## Project Summary

This repo is a local Japanese reading site. Article source data lives in JSON, and static HTML pages are generated from that data.

## Current Layout

- [index.html](/Users/zijianzh/repositories/learn-japanese/index.html)
  Generated archive page.
- `2026-*.html`
  Generated article pages kept at the repo root for stable URLs.
- [data/articles.json](/Users/zijianzh/repositories/learn-japanese/data/articles.json)
  Ordered manifest of article JSON files.
- [data/articles/](/Users/zijianzh/repositories/learn-japanese/data/articles)
  Per-article JSON source files.
- [templates/article.html](/Users/zijianzh/repositories/learn-japanese/templates/article.html)
  Article page template.
- [assets/article.css](/Users/zijianzh/repositories/learn-japanese/assets/article.css)
  Shared styles.
- [assets/article.js](/Users/zijianzh/repositories/learn-japanese/assets/article.js)
  Shared navigation, playback, highlighting, copy, and recording behavior.
- [scripts/generate_site.py](/Users/zijianzh/repositories/learn-japanese/scripts/generate_site.py)
  Regenerates the static pages and article navigation.
- [server/local_tts_server.py](/Users/zijianzh/repositories/learn-japanese/server/local_tts_server.py)
  Static HTTP server, VOICEVOX proxy, and MP4 conversion endpoint.

## Editing Rules

- Edit article content in `data/articles/*.json`, not directly in generated `2026-*.html` files.
- Keep article ordering in `data/articles.json`.
- After changing article data or `templates/article.html`, run:

```bash
python3 scripts/generate_site.py
```

- Commit generated changes together with the source data/template change.
- Keep root article HTML filenames stable unless intentionally changing URLs.

## Runtime Behavior

Article pages support:

- furigana via `ruby`
- copy-to-clipboard without `rt` furigana text
- browser `speechSynthesis` playback
- Docker VOICEVOX playback through the local server
- sentence-level highlighting
- icon-only top navigation
- desktop and mobile article navigation
- vertical one-page recording mode
- MP4 download through browser support or server-side `ffmpeg` conversion

## Run

```bash
docker compose up --build
```

Open:

```text
http://127.0.0.1:8765/index.html
```

Local Python mode:

```bash
python3 server/local_tts_server.py
```

## Verify

Use these checks after code, data, template, or Docker changes:

```bash
python3 scripts/generate_site.py
node --check assets/article.js
python3 -m py_compile server/local_tts_server.py scripts/generate_site.py
docker compose config
```

Manual checks:

- archive page loads
- article page loads
- navigation renders on desktop and mobile
- copy excludes furigana text
- voice source switching works
- `Read Aloud` highlights one sentence at a time
- `Render Video` enters the vertical recording layout and downloads MP4 when conversion succeeds
