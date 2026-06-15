# Japanese learning board

A local Japanese learning board with furigana, sentence highlighting, browser speech playback, Docker VOICEVOX playback, copy-to-clipboard, and MP4-oriented tab recording.

## Project Layout

- `index.html`: generated reading archive and article index.
- `ig-videos.html`: story quiz video generator for Instagram-style vertical MP4s.
- `2026-*.html`: generated article pages kept at the repo root so URLs stay simple.
- `data/articles.json`: ordered manifest of article JSON files.
- `data/article-navigation.json`: generated runtime navigation manifest for article pages.
- `data/articles/*.json`: source files for article content, metadata, translations, and vocabulary.
- `templates/article.html`: article page template.
- `assets/article.css`: shared article styles.
- `assets/article.js`: shared article behavior, navigation, playback, highlighting, and recording.
- `assets/ig-videos.css` and `assets/ig-videos.js`: story quiz video generator styles and behavior.
- `data/video-quizzes.json`: source content for short Japanese quiz passages, translations, questions, and options.
- `scripts/generate_site.py`: static site generator.
- `scripts/render_video_url.py`: CLI renderer that writes an MP4 under `videos/` and prints a JSON download URL.
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
python3 -m py_compile server/local_tts_server.py scripts/generate_site.py scripts/render_video.py scripts/render_video_url.py scripts/voicevox_cache.py scripts/generate_audio_cache.py
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
- `data/article-navigation.json`
- `data/flashcards.json`

## Features

- Browser voice playback through `speechSynthesis`.
- Docker VOICEVOX playback through the local server:
  - `GET /api/tts/voicevox/status`
  - `POST /api/tts/voicevox`
  - `POST /api/tts/voicevox/cache-status`
  - Generated WAV files are cached under `.generated_audio/voicevox/` by speaker and content hash.
- Flashcard progress through the local server:
  - `GET /api/flashcards/progress`
  - `POST /api/flashcards/progress`
  - Progress is stored in `data/flashcard-progress.json`, which is ignored by git.
  - If server progress is empty, the flashcards page migrates older browser-only progress to the server once.
- Video rendering through the local server:
  - `POST /api/video/render` streams an MP4 response.
  - `POST /api/video/render-url` writes the MP4 to `videos/` and returns JSON with `download_url`.
  - `POST /api/video/render-quiz-url` writes a multiple-choice story quiz MP4 to `videos/` and returns JSON with `download_url`.
- Voice source, browser voice, and Docker speaker preferences persist across refreshes and article pages.
- Sentence-level highlighting during playback.
- Furigana-safe article copy.
- Flashcards show common verb forms next to the base vocabulary.
- Flashcards cycle through five generated or source-provided example sentences per card, with the next example index stored in progress.
- Story quiz videos render a 9:16 multiple-choice prompt with four answers and Japanese TTS narration while keeping the full JP/EN passage available for comment copying.
- Vertical one-page recording layout for `Render Video`.
- MP4 download when browser MP4 recording is available or server-side `ffmpeg` conversion succeeds.

Render a video from the command line and print a JSON download URL:

```bash
python3 scripts/render_video_url.py 2026-06-10-bear-capture-drone --pretty
```

Pre-generate cached VOICEVOX audio for all article sentences and flashcard terms/examples:

```bash
python3 scripts/generate_audio_cache.py
```

Limit generation to one area when needed:

```bash
python3 scripts/generate_audio_cache.py --articles
python3 scripts/generate_audio_cache.py --flashcards
```

Use `PUBLIC_BASE_URL` or `--base-url` if the static server is exposed somewhere other than `http://127.0.0.1:8765`.

## Verify

```bash
python3 scripts/generate_site.py
node --check assets/article.js
python3 -m py_compile server/local_tts_server.py scripts/generate_site.py scripts/render_video.py scripts/render_video_url.py
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
