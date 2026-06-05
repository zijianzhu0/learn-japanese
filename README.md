# Learn Japanese Reading Pages

A small local Japanese reading site with article pages, furigana, browser speech playback, sentence highlighting, copy-to-clipboard, and browser-based recording.

## Architecture

- `index.html` is the reading archive and article index.
- `2026-*.html` files are individual article pages.
- `article-template.html` is the reusable article page template.
- `article.css` contains shared article, toolbar, navigation, highlighting, and recording styles.
- `article.js` contains shared article behavior:
  - top and article navigation generation
  - furigana-safe text extraction
  - sentence splitting and highlighting
  - copy-to-clipboard
  - browser `speechSynthesis` playback
  - Docker VOICEVOX TTS playback
  - tab recording flow for video export
- `local_tts_server.py` serves the static site on `127.0.0.1:8765` and proxies local VOICEVOX requests.
- `docker-compose.yml` starts the local VOICEVOX engine on `127.0.0.1:50021`.

## Run The Site

```bash
python3 local_tts_server.py
```

Open:

```text
http://127.0.0.1:8765/index.html
```

## Browser Voice Playback

Article pages add a `Voice Source` dropdown to the toolbar. Choose `Browser Voice`, then use `Read Aloud` to play the article with the selected browser voice.

The preferred browser voice is `Google 日本語` when the browser exposes it. If it is not available, the page falls back to another Japanese voice from the dropdown.

## Docker VOICEVOX TTS

Start VOICEVOX:

```bash
docker compose up -d voicevox
```

Then start the site server if it is not already running:

```bash
python3 local_tts_server.py
```

Article pages add `Docker VOICEVOX` to the `Voice Source` dropdown. When selected, the toolbar shows a `Docker Voice` dropdown populated from VOICEVOX speakers and styles.

The Docker path generates sentence-level WAV audio through the local server:

- `GET /api/tts/voicevox/status`
- `POST /api/tts/voicevox`

The default speaker is VOICEVOX speaker `3`. Once VOICEVOX is reachable, `Read Aloud` and `Render Video` use the selected Docker speaker.

Stop VOICEVOX when done:

```bash
docker compose down
```

## Video Rendering

`Render Video` records the current browser tab with sentence highlighting. During recording, the page switches to a fixed vertical 9:16 one-page composition: navigation, toolbar controls, status text, translations, source notes, and vocabulary UI are hidden, and the Japanese article is fit onto one page without scrolling.

`Render Video` uses the selected `Voice Source`. With `Docker VOICEVOX` selected, video rendering prepares Docker TTS sentence audio first and uses it for narration. With `Browser Voice` selected, rendering uses browser speech playback.

The recording page uses a centered vertical `9:16` aspect ratio and scales to the captured tab. Browser tab capture still controls the final video file dimensions, but the captured content is a centered one-page layout instead of a scrolling reading page.

To preview the recording layout without opening the capture prompt, add `?recording-preview=1` to any article URL.

When the browser prompts for capture permissions:

- share the current tab
- enable tab audio if the browser offers it

## Verification

Basic checks:

```bash
node --check article.js
python3 -m py_compile local_tts_server.py
docker compose config
```

VOICEVOX proxy smoke test:

```bash
curl -s -i http://127.0.0.1:8765/api/tts/voicevox/status
curl -s -f \
  -H 'Content-Type: application/json' \
  -X POST \
  --data '{"text":"今日はテストです。","speaker":3}' \
  http://127.0.0.1:8765/api/tts/voicevox \
  -o /tmp/learn-japanese-voicevox-test.wav
```

Manual page checks:

- archive page loads without console errors
- article page top navigation renders
- desktop article navigation renders
- mobile hamburger navigation renders
- `Copy Japanese Article` excludes furigana text
- `Voice Source` switches between browser and Docker voice controls
- `Read Aloud` highlights one sentence at a time with the selected source
- `Render Video` switches to text-only recording mode and downloads `.mp4` using browser MP4 recording when available, or local `ffmpeg` conversion from WebM when needed

## Known Limitation

Browser `speechSynthesis` audio is not reliably capturable as tab audio. The Docker VOICEVOX path exists to test file-backed narration for more reliable video export audio.
