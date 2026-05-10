# AGENTS.md

## Overview

This repo is a small local Japanese reading page project.

The current primary artifact is:

- [2026年5月10日.html](/Users/zijianzh/repositories/learn-japanese/2026年5月10日.html)

That page currently supports:

- mobile-friendly reading layout
- furigana via `ruby`
- copy-to-clipboard for the article text
- browser speech playback
- sentence highlighting during playback
- browser voice selection
- browser-based tab recording flow for video capture

## File Tree

Important files and directories:

- [2026年5月10日.html](/Users/zijianzh/repositories/learn-japanese/2026年5月10日.html)
  Main article page. This is the file to edit for UI, voice playback, highlighting, and video capture behavior.

- [article-template.html](/Users/zijianzh/repositories/learn-japanese/article-template.html)
  Reusable HTML template derived from the original article page styling.

- [local_tts_server.py](/Users/zijianzh/repositories/learn-japanese/local_tts_server.py)
  Very small static HTTP server for serving the repo on `127.0.0.1:8765`.

- [export_speech.swift](/Users/zijianzh/repositories/learn-japanese/export_speech.swift)
  Experimental macOS speech-export helper. This was added while testing file-backed speech export for video rendering. It is not currently part of the working path.

- [models](/Users/zijianzh/repositories/learn-japanese/models)
  Leftover local Piper/Piper Plus model downloads from earlier experiments. The current page no longer depends on them.

- [.generated_audio](/Users/zijianzh/repositories/learn-japanese/.generated_audio)
  Leftover generated WAV files from earlier Piper sync experiments. The current page no longer depends on them.

- [.venv](/Users/zijianzh/repositories/learn-japanese/.venv)
  Older Python venv from earlier experimentation.

- [.venv311](/Users/zijianzh/repositories/learn-japanese/.venv311)
  Python 3.11 venv used during the Piper/Piper Plus exploration.

## Current Behavior

The current page is browser-voice-only.

Important details:

- The previous Piper flow was removed from the page logic.
- The preferred default browser voice is `Google 日本語` if the browser exposes it.
- If `Google 日本語` is unavailable, the page falls back to the next available Japanese voice in the dropdown.
- Sentence highlighting is driven by queueing one sentence per `SpeechSynthesisUtterance`.

## How To Run

Start the local server from the repo root:

```bash
cd /Users/zijianzh/repositories/learn-japanese
python3 local_tts_server.py
```

Then open:

- [http://127.0.0.1:8765/2026%E5%B9%B45%E6%9C%8810%E6%97%A5.html](http://127.0.0.1:8765/2026%E5%B9%B45%E6%9C%8810%E6%97%A5.html)

## How To Test

### 1. Basic Page Load

Confirm that:

- the page loads without console errors
- the layout is readable on a narrow viewport
- furigana renders correctly

### 2. Copy Button

Press `Copy Japanese Article` and confirm:

- clipboard contains the headline and article body
- furigana `rt` text is not included

### 3. Voice Playback

Choose a browser voice from the dropdown.

Recommended test:

- `Google 日本語` if available

Press `Read Aloud` and confirm:

- playback starts
- one sentence is highlighted at a time
- the button toggles to stop behavior during playback

### 4. Sentence Highlighting

While playback runs, confirm:

- highlighting advances sentence by sentence
- the currently spoken sentence scrolls into view if needed

### 5. Video Rendering

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

### Local macOS Export Attempts Are Not Working Yet

Several local export paths were explored:

- shell `say`
- `NSSpeechSynthesizer`
- `AVSpeechSynthesizer.write(...)`

None of them produced a reliable file-backed Japanese audio export in the current setup.

### Experimental Files Remain In The Repo

These are currently historical/experimental:

- [export_speech.swift](/Users/zijianzh/repositories/learn-japanese/export_speech.swift)
- [models](/Users/zijianzh/repositories/learn-japanese/models)
- [.generated_audio](/Users/zijianzh/repositories/learn-japanese/.generated_audio)
- [.venv](/Users/zijianzh/repositories/learn-japanese/.venv)
- [.venv311](/Users/zijianzh/repositories/learn-japanese/.venv311)

They can be cleaned up later if the repo should only contain the working browser-voice path.

## TODOs

### High Priority

- Make `Render Video` include reliable narration audio.
- Decide whether to keep browser speech only, or reintroduce a file-backed render-only TTS path.
- Verify whether the in-app browser can capture browser speech under any specific share/capture mode.

### Medium Priority

- Hide or remove the unused `<audio>` player if it is no longer needed.
- Remove old Piper-specific artifacts if the project is officially browser-voice-only.
- Make the voice dropdown label more explicit, for example `Browser Voice`.

### Low Priority

- Add a second article using the template.
- Add a cleaner page-level recording mode style.
- Add a small inline status indicator for the selected voice.

## Suggested Next Step

If the goal is “export a narrated highlighted video,” the next concrete engineering move is:

- use browser voices for live reading
- use a separate file-backed TTS source only for export/render

That split reflects the current technical reality better than trying to force `speechSynthesis` output into a recorded tab audio track.
