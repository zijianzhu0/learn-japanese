# AGENTS.md

## Overview

This repo is a small local Japanese reading page project.

The current primary artifacts are:

- [index.html](/Users/zijianzh/repositories/learn-japanese/index.html)
  Blog-style reading archive. Edit this for the index/archive layout and index navigation.
- Individual `2026-*.html` article pages.
  Edit these for article UI, voice playback, highlighting, and video capture behavior.
- [article-template.html](/Users/zijianzh/repositories/learn-japanese/article-template.html)
  Reusable article template. Keep this in sync with article-page navigation and behavior.

Current pages support:

- mobile-friendly reading layout
- furigana via `ruby`
- copy-to-clipboard for the article text
- browser speech playback
- sentence highlighting during playback
- browser voice selection
- browser-based tab recording flow for video capture
- icon-only top navigation
- desktop left article navigation
- mobile hamburger article navigation

## File Tree

Important files:

- [index.html](/Users/zijianzh/repositories/learn-japanese/index.html)
  Blog archive page with article links. Desktop shows left navigation; narrow screens fold article navigation behind a hamburger icon.

- [article-template.html](/Users/zijianzh/repositories/learn-japanese/article-template.html)
  Reusable HTML template for article pages. It includes the same top icon nav and left/mobile article navigation used by current article pages.

- [local_tts_server.py](/Users/zijianzh/repositories/learn-japanese/local_tts_server.py)
  Very small static HTTP server for serving the repo on `127.0.0.1:8765`.

- `2026-*.html`
  Individual article pages. Each page is self-contained and includes its own article CSS, navigation CSS, and speech/copy/recording JavaScript.

Removed cleanup artifacts:

- `export_speech.swift`
- `models/`
- `.generated_audio/`
- `.venv/`
- `.venv311/`
- `__pycache__/`

## Current Behavior

The current app is browser-voice-only.

Important details:

- The previous Piper flow was removed from the page logic.
- The preferred default browser voice is `Google 日本語` if the browser exposes it.
- If `Google 日本語` is unavailable, the page falls back to the next available Japanese voice in the dropdown.
- Sentence highlighting is driven by queueing one sentence per `SpeechSynthesisUtterance`.
- Top navigation uses inline SVG icons, not CSS-drawn icons or external icon libraries.
- Article pages use file links in the left navigation. The current article link is marked with `aria-current="page"`.
- Mobile article navigation uses a `<details>` hamburger menu and swaps to an X icon when open.

## How To Run

Start the local server from the repo root:

```bash
cd /Users/zijianzh/repositories/learn-japanese
python3 local_tts_server.py
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
- a `.webm` download is triggered when recording finishes

Important note:

- the video may still be silent when using browser/system speech voices, because `speechSynthesis` output is often not capturable as tab audio

## Known Limitations

### Browser Voice Audio Is Not Reliably Recordable

Live playback works.

Recorded video audio is not reliable with `speechSynthesis` voices such as `Google 日本語`, because that audio is usually not exposed to the page as a capturable media stream.

### File-Backed Export Is Not Implemented

Several local export paths were explored earlier:

- shell `say`
- `NSSpeechSynthesizer`
- `AVSpeechSynthesizer.write(...)`

Those experiments were removed from the working repo. Reintroduce a file-backed render-only TTS path only if reliable narrated export becomes the goal again.

## TODOs

### High Priority

- Make `Render Video` include reliable narration audio.
- Decide whether to keep browser speech only, or reintroduce a file-backed render-only TTS path.
- Verify whether the in-app browser can capture browser speech under any specific share/capture mode.

### Medium Priority

- Hide or remove the unused `<audio>` player if it is no longer needed.
- Keep `article-template.html` synchronized with article page navigation.
- Consider extracting shared navigation generation if article count grows further.

### Low Priority

- Add more articles using the template.
- Add a cleaner page-level recording mode style.
- Add a small inline status indicator for the selected voice.

## Suggested Next Step

If the goal is “export a narrated highlighted video,” the next concrete engineering move is:

- use browser voices for live reading
- use a separate file-backed TTS source only for export/render

That split reflects the current technical reality better than trying to force `speechSynthesis` output into a recorded tab audio track.
