# AGENTS.md

## Overview

This repo is a small local Japanese reading page project.

The current primary artifacts are:

- [index.html](/Users/zijianzh/repositories/learn-japanese/index.html)
  Blog-style reading archive. Edit this for the index/archive layout and index navigation.
- Individual `2026-*.html` article pages.
  Edit these for article UI, voice playback, highlighting, and video capture behavior.
- [templates/article.html](/Users/zijianzh/repositories/learn-japanese/templates/article.html)
  Reusable article template. Keep this in sync with article-page navigation and behavior.
- [assets/article.css](/Users/zijianzh/repositories/learn-japanese/assets/article.css)
  Shared article, toolbar, navigation, highlighting, and recording styles.
- [assets/article.js](/Users/zijianzh/repositories/learn-japanese/assets/article.js)
  Shared article behavior, navigation generation, speech playback, VOICEVOX playback, highlighting, and recording.
- [data/articles.json](/Users/zijianzh/repositories/learn-japanese/data/articles.json)
  Ordered article manifest.
- [data/articles/](/Users/zijianzh/repositories/learn-japanese/data/articles)
  Per-article JSON source files for article metadata, content, translations, and vocabulary.
- [scripts/generate_site.py](/Users/zijianzh/repositories/learn-japanese/scripts/generate_site.py)
  Regenerates article pages, the archive page, and shared article navigation from the article manifest.

Current pages support:

- mobile-friendly reading layout
- furigana via `ruby`
- copy-to-clipboard for the article text
- browser speech playback
- Docker VOICEVOX playback through the local server
- sentence highlighting during playback
- browser voice selection
- browser-based tab recording flow with MP4 conversion
- icon-only top navigation
- desktop left article navigation
- mobile hamburger article navigation

## File Tree

Important files:

- [index.html](/Users/zijianzh/repositories/learn-japanese/index.html)
  Blog archive page with article links. Desktop shows left navigation; narrow screens fold article navigation behind a hamburger icon.

- [templates/article.html](/Users/zijianzh/repositories/learn-japanese/templates/article.html)
  Reusable HTML template for article pages. It includes the same top icon nav and left/mobile article navigation used by current article pages.

- [server/local_tts_server.py](/Users/zijianzh/repositories/learn-japanese/server/local_tts_server.py)
  Static HTTP server for serving the repo on `127.0.0.1:8765`, proxying VOICEVOX, and converting recordings to MP4.

- `2026-*.html`
  Generated individual article pages. Each page loads shared assets from `assets/`.

Removed cleanup artifacts:

- `export_speech.swift`
- `models/`
- `.generated_audio/`
- `.venv/`
- `.venv311/`
- `__pycache__/`

## Current Behavior

The current app supports browser voices and Docker VOICEVOX.

Important details:

- The previous Piper flow was removed from the page logic.
- The preferred default browser voice is `Google 日本語` if the browser exposes it.
- If `Google 日本語` is unavailable, the page falls back to the next available Japanese voice in the dropdown.
- The `Voice Source` dropdown switches between browser `speechSynthesis` and Docker VOICEVOX.
- Sentence highlighting is driven by sentence-level playback units.
- `Render Video` uses a vertical recording mode and downloads MP4 when browser support or server-side conversion is available.
- Top navigation uses inline SVG icons, not CSS-drawn icons or external icon libraries.
- Article pages use file links in the left navigation. The current article link is marked with `aria-current="page"`.
- Mobile article navigation uses a `<details>` hamburger menu and swaps to an X icon when open.

## How To Run

Start the local server from the repo root:

```bash
cd /Users/zijianzh/repositories/learn-japanese
python3 server/local_tts_server.py
```

Then open:

- [http://127.0.0.1:8765/index.html](http://127.0.0.1:8765/index.html)

## How To Test

### 1. Index Page

Confirm that:

- the page loads without console errors
- the icon-only top navigation renders cleanly
- desktop shows the left article navigation
- narrow screens show a hamburger article menu
- article links open the expected article pages

### 2. Article Page Load

Confirm that:

- the article page loads without console errors
- the top icon navigation is visible
- desktop shows the left article navigation
- narrow screens show the hamburger article menu
- the current article is highlighted in the left navigation
- furigana renders correctly

### 3. Copy Button

Press `Copy Japanese Article` and confirm:

- clipboard contains the headline and article body
- furigana `rt` text is not included

### 4. Voice Playback

Choose a browser voice from the dropdown.

Recommended test:

- `Google 日本語` if available

Press `Read Aloud` and confirm:

- playback starts
- one sentence is highlighted at a time
- the button toggles to stop behavior during playback

### 5. Sentence Highlighting

While playback runs, confirm:

- highlighting advances sentence by sentence
- the currently spoken sentence scrolls into view if needed

### 6. Video Rendering

Press `Render Video`.

When prompted by the browser:

- share the current tab
- enable tab audio if the browser offers it

Confirm:

- the toolbar disappears during recording
- sentence highlighting is visible in the captured page
- an `.mp4` download is triggered when browser MP4 recording or local conversion succeeds

Important note:

- browser voice videos may still be silent because `speechSynthesis` output is often not capturable as tab audio

## Known Limitations

### Browser Voice Audio Is Not Reliably Recordable

Live playback works.

Recorded video audio is not reliable with `speechSynthesis` voices such as `Google 日本語`, because that audio is usually not exposed to the page as a capturable media stream.

### MP4 Conversion Requires ffmpeg

Docker installs `ffmpeg`. Local Python development needs `ffmpeg` on `PATH` for server-side MP4 conversion.

## TODOs

### High Priority

- Continue validating Docker VOICEVOX narration for video export.
- Verify whether the in-app browser can capture browser speech under any specific share/capture mode.

### Medium Priority

- Hide or remove the unused `<audio>` player if it is no longer needed.
- Keep `templates/article.html` synchronized with article page navigation.
- Consider extracting shared navigation generation if article count grows further.

### Low Priority

- Add more articles using the template.
- Add a small inline status indicator for the selected voice.
