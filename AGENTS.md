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
- [data/article-navigation.json](/Users/zijianzh/repositories/learn-japanese/data/article-navigation.json)
  Generated runtime navigation manifest for article pages.
- [data/articles/](/Users/zijianzh/repositories/learn-japanese/data/articles)
  Per-article JSON source files.
- [templates/article.html](/Users/zijianzh/repositories/learn-japanese/templates/article.html)
  Article page template.
- [assets/article.css](/Users/zijianzh/repositories/learn-japanese/assets/article.css)
  Shared styles.
- [assets/article.js](/Users/zijianzh/repositories/learn-japanese/assets/article.js)
  Shared navigation, playback, highlighting, copy, and recording behavior.
- [scripts/generate_site.py](/Users/zijianzh/repositories/learn-japanese/scripts/generate_site.py)
  Regenerates the static pages, flashcards manifest, and article navigation manifest.
- [server/local_tts_server.py](/Users/zijianzh/repositories/learn-japanese/server/local_tts_server.py)
  Static HTTP server, VOICEVOX proxy, and MP4 conversion endpoint.

## Editing Rules

- Edit article content in `data/articles/*.json`, not directly in generated `2026-*.html` files.
- Keep article ordering in `data/articles.json`.
- Before starting a substantial change, create a feature branch and make the work there.
- When a change is complete, or when starting a new feature, start a fresh branch rather than continuing on an old one.
- After changing article data or `templates/article.html`, run:

```bash
python3 scripts/generate_site.py
```

- Commit generated changes together with the source data/template change.
- Keep root article HTML filenames stable unless intentionally changing URLs.

## News Selection

- When adding new articles, prefer recent Japan news with unusual, surprising, or slightly unhinged angles over routine policy or business coverage.
- Good candidates include strange civic incidents, unexpected public responses, odd official moments, unusual festivals, animal intrusions, novelty technology in daily life, and other stories that feel memorable or off-center while still being factual.
- Keep the tone of the article itself clear and readable for learners. The story choice can be weird; the writing should stay straightforward.
- Use primary or high-quality news sources when possible, and keep source notes accurate to the publication date of the original report.

## Article Length

- Keep each article compact.
- The combined total of the Japanese body text and the English translations should stay under 2000 characters.
- When shortening is necessary, simplify the English first. The English can be more direct and less detailed than the Japanese as long as it stays accurate.

## Runtime Behavior

Article pages support:

- furigana via `ruby`
- copy-to-clipboard without `rt` furigana text
- browser `speechSynthesis` playback
- Docker VOICEVOX playback through the local server
- persisted voice source, browser voice, and Docker speaker preferences
- sentence-level highlighting
- icon-only top navigation
- desktop and mobile article navigation
- vertical one-page recording mode
- MP4 download through browser support or server-side `ffmpeg` conversion

## Recording Layout Guidelines

- The recording render uses the `body.recording-mode` rules in `assets/article.css` as the source of truth for preview and export layout.
- Keep the render frame at `1080x1920` unless intentionally changing the output format.
- Treat `body.recording-mode .container` padding as the canonical content inset for the title and body copy. The current layout uses an intentionally asymmetric inset with a larger left padding than right padding.
- Keep recording-mode title and paragraph elements free of extra horizontal padding so they align to the shared `.container` inset.
- The recording background is a textured paper treatment built from layered gradients plus the `.container::before` grid overlay. Update those recording-only layers instead of the global page background when adjusting video render texture.
- Keep `.container > *` above the texture overlay so the text remains readable in preview and export.
- The recording footer is centered and stacked vertically. If footer spacing changes, update `body.recording-mode .recording-footer` rather than adding per-span positioning.
- Paragraph spacing in renders comes from `body.recording-mode p { margin-bottom: ... }`, while intra-paragraph line spacing comes from `--recording-body-line-height`.
- Video render caching is versioned in `server/local_tts_server.py`. Bump the video render cache version when CSS or render changes should force fresh MP4 output.

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

If `docker compose` is already up with both containers running, you do not need to start the web server again on a different port.

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
