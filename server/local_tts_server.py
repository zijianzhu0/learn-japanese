#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import parse

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scripts.render_video import (
    DEFAULT_VOICEVOX_TIMEOUT,
    RenderOptions,
    find_article,
    find_video_quiz,
    quiz_video_filename,
    render_article_video,
    render_quiz_video,
)
from scripts.voicevox_cache import (
    VoicevoxRequestError,
    cache_path,
    cached_voicevox_wav,
    voicevox_request,
)


DEFAULT_HOST = os.environ.get("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT", "8765"))
DEFAULT_PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "127.0.0.1")
VOICEVOX_BASE_URL = os.environ.get("VOICEVOX_BASE_URL", "http://127.0.0.1:50021")
DEFAULT_VOICEVOX_SPEAKER = 9
MAX_TTS_TEXT_CHARS = 500
MAX_VIDEO_UPLOAD_BYTES = 700 * 1024 * 1024
VIDEO_OUTPUT_DIR = PROJECT_DIR / "videos"
FLASHCARD_PROGRESS_PATH = PROJECT_DIR / "data" / "flashcard-progress.json"
FLASHCARD_PROGRESS_LOCK = threading.Lock()


class LearnJapaneseHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        request_path = parse.urlsplit(self.path).path
        if request_path == "/api/tts/voicevox/status":
            self.handle_voicevox_status()
            return

        if request_path == "/api/flashcards/progress":
            self.handle_flashcard_progress_get()
            return

        super().do_GET()

    def do_POST(self) -> None:
        request_path = parse.urlsplit(self.path).path
        if request_path == "/api/tts/voicevox":
            self.handle_voicevox_synthesis()
            return

        if request_path == "/api/tts/voicevox/cache-status":
            self.handle_voicevox_cache_status()
            return

        if request_path == "/api/flashcards/progress":
            self.handle_flashcard_progress_update()
            return

        if request_path == "/api/video/convert-mp4":
            self.handle_mp4_conversion()
            return

        if request_path == "/api/video/render":
            self.handle_video_render()
            return

        if request_path == "/api/video/render-url":
            self.handle_video_render_url()
            return

        if request_path == "/api/video/render-quiz-url":
            self.handle_quiz_video_render_url()
            return

        self.send_json(404, {"ok": False, "error": "Unknown API endpoint."})

    def handle_voicevox_status(self) -> None:
        try:
            speakers = voicevox_request("GET", "/speakers", base_url=VOICEVOX_BASE_URL)
        except VoicevoxRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return

        self.send_json(
            200,
            {
                "ok": True,
                "engine": "VOICEVOX",
                "base_url": VOICEVOX_BASE_URL,
                "default_speaker": DEFAULT_VOICEVOX_SPEAKER,
                "speakers": speakers,
            },
        )

    def handle_voicevox_synthesis(self) -> None:
        try:
            payload = self.read_json_body()
            text = str(payload.get("text", "")).strip()
            speaker = int(payload.get("speaker", DEFAULT_VOICEVOX_SPEAKER))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": f"Invalid JSON request: {exc}"})
            return

        if not text:
            self.send_json(400, {"ok": False, "error": "Missing text."})
            return

        if len(text) > MAX_TTS_TEXT_CHARS:
            self.send_json(
                413,
                {
                    "ok": False,
                    "error": f"Text is too long. Limit is {MAX_TTS_TEXT_CHARS} characters.",
                },
            )
            return

        try:
            wav_audio, cache_hit, cache_file = cached_voicevox_wav(
                text,
                speaker,
                base_url=VOICEVOX_BASE_URL,
            )
        except VoicevoxRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return

        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(wav_audio)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("X-Audio-Cache", "hit" if cache_hit else "miss")
        self.send_header("X-Audio-Cache-Key", cache_file.stem)
        self.end_headers()
        self.wfile.write(wav_audio)

    def handle_voicevox_cache_status(self) -> None:
        try:
            payload = self.read_json_body()
            raw_texts = payload.get("texts")
            if raw_texts is None:
                raw_texts = [payload.get("text", "")]
            if not isinstance(raw_texts, list):
                raise TypeError("texts must be an array")
            speaker = int(payload.get("speaker", DEFAULT_VOICEVOX_SPEAKER))
            texts = [str(text).strip() for text in raw_texts]
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": f"Invalid JSON request: {exc}"})
            return

        if len(texts) > 100:
            self.send_json(413, {"ok": False, "error": "Too many texts. Limit is 100."})
            return

        results = []
        cached_count = 0
        for index, text in enumerate(texts):
            if not text:
                results.append({"index": index, "cached": False, "cache": "missing", "key": ""})
                continue
            if len(text) > MAX_TTS_TEXT_CHARS:
                self.send_json(
                    413,
                    {
                        "ok": False,
                        "error": f"Text is too long. Limit is {MAX_TTS_TEXT_CHARS} characters.",
                    },
                )
                return
            path = cache_path(text, speaker)
            cached = path.exists()
            if cached:
                cached_count += 1
            results.append(
                {
                    "index": index,
                    "cached": cached,
                    "cache": "hit" if cached else "miss",
                    "key": path.stem,
                }
            )

        self.send_json(
            200,
            {
                "ok": True,
                "speaker": speaker,
                "cached": cached_count,
                "missing": len(results) - cached_count,
                "results": results,
            },
        )

    def handle_flashcard_progress_get(self) -> None:
        try:
            with FLASHCARD_PROGRESS_LOCK:
                progress = self.read_flashcard_progress()
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json(500, {"ok": False, "error": f"Progress could not be loaded: {exc}"})
            return
        self.send_json(200, {"ok": True, **progress})

    def handle_flashcard_progress_update(self) -> None:
        try:
            payload = self.read_json_body()
            operation = str(payload.get("operation", "")).strip()
        except (TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": f"Invalid JSON request: {exc}"})
            return

        try:
            with FLASHCARD_PROGRESS_LOCK:
                progress = self.read_flashcard_progress()
                if operation == "put":
                    store = self.progress_store_name(payload)
                    record = self.progress_record(payload)
                    progress[store] = self.upsert_progress_record(store, progress[store], record)
                elif operation == "add":
                    store = self.progress_store_name(payload)
                    record = self.progress_record(payload)
                    progress[store] = self.upsert_progress_record(store, progress[store], record)
                elif operation == "clear":
                    store = self.progress_store_name(payload)
                    progress[store] = []
                elif operation == "replace":
                    progress["cards"] = self.progress_record_list(payload.get("cards", []))
                    progress["reviews"] = self.progress_record_list(payload.get("reviews", []))
                elif operation == "reset":
                    progress["cards"] = []
                    progress["reviews"] = []
                else:
                    raise ValueError("Unsupported progress operation.")

                self.write_flashcard_progress(progress)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return

        self.send_json(200, {"ok": True, **progress})

    def read_flashcard_progress(self) -> dict:
        if not FLASHCARD_PROGRESS_PATH.exists():
            return {"schemaVersion": 2, "cards": [], "reviews": []}

        payload = json.loads(FLASHCARD_PROGRESS_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Progress file must contain a JSON object.")

        cards = self.progress_record_list(payload.get("cards", []))
        reviews = self.progress_record_list(payload.get("reviews", []))
        return {"schemaVersion": 2, "cards": cards, "reviews": reviews}

    def write_flashcard_progress(self, progress: dict) -> None:
        FLASHCARD_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = FLASHCARD_PROGRESS_PATH.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(FLASHCARD_PROGRESS_PATH)

    def progress_store_name(self, payload: dict) -> str:
        store = str(payload.get("store", "")).strip()
        if store not in {"cards", "reviews"}:
            raise ValueError("Progress store must be cards or reviews.")
        return store

    def progress_record(self, payload: dict) -> dict:
        record = payload.get("record")
        if not isinstance(record, dict):
            raise ValueError("Progress record must be an object.")
        return record

    def progress_record_list(self, value: object) -> list[dict]:
        if not isinstance(value, list):
            raise ValueError("Progress records must be an array.")
        if not all(isinstance(item, dict) for item in value):
            raise ValueError("Each progress record must be an object.")
        return value

    def upsert_progress_record(self, store: str, records: list[dict], record: dict) -> list[dict]:
        key = "card_id" if store == "cards" else "id"
        record_id = str(record.get(key, "")).strip()
        if not record_id:
            raise ValueError(f"Progress record is missing {key}.")

        updated = False
        next_records = []
        for existing in records:
            if str(existing.get(key, "")).strip() == record_id:
                next_records.append(
                    self.merge_card_progress(existing, record) if store == "cards" else record
                )
                updated = True
            else:
                next_records.append(existing)
        if not updated:
            next_records.append(record)
        return next_records

    def merge_card_progress(self, existing: dict, incoming: dict) -> dict:
        merged = {**existing, **incoming}
        for key in ("shown_count", "remembered_count", "forgot_count"):
            merged[key] = max(int(existing.get(key) or 0), int(incoming.get(key) or 0))

        for key in ("last_shown_at", "last_answered_at"):
            merged[key] = max(str(existing.get(key) or ""), str(incoming.get(key) or "")) or None

        existing_answered = str(existing.get("last_answered_at") or "")
        incoming_answered = str(incoming.get("last_answered_at") or "")
        schedule_source = incoming if incoming_answered >= existing_answered else existing
        for key in ("due_at", "interval_days", "ease_factor", "state"):
            merged[key] = schedule_source.get(key)

        return merged

    def handle_mp4_conversion(self) -> None:
        if not shutil.which("ffmpeg"):
            self.send_json(503, {"ok": False, "error": "ffmpeg is not installed or not on PATH."})
            return

        try:
            source_video = self.read_binary_body(MAX_VIDEO_UPLOAD_BYTES)
        except ValueError as exc:
            self.send_json(413, {"ok": False, "error": str(exc)})
            return

        if not source_video:
            self.send_json(400, {"ok": False, "error": "Missing video data."})
            return

        try:
            with tempfile.TemporaryDirectory(prefix="learn-japanese-video-") as temp_dir:
                temp_path = Path(temp_dir)
                input_path = temp_path / "input.webm"
                output_path = temp_path / "output.mp4"
                input_path.write_bytes(source_video)

                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(input_path),
                        "-vf",
                        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        "veryfast",
                        "-movflags",
                        "+faststart",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "160k",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                )
                mp4_video = output_path.read_bytes()
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
            self.send_json(500, {"ok": False, "error": f"ffmpeg conversion failed: {detail}"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(mp4_video)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(mp4_video)

    def handle_video_render(self) -> None:
        try:
            article, output_path, temp_dir = self.render_video_to_temp_file()
            try:
                mp4_video = output_path.read_bytes()
            finally:
                temp_dir.cleanup()
        except VideoRenderRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return

        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(mp4_video)))
        self.send_header("Content-Disposition", f'attachment; filename="{article["downloadFileName"]}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(mp4_video)

    def handle_video_render_url(self) -> None:
        try:
            article, temp_output_path, temp_dir = self.render_video_to_temp_file()
            VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = VIDEO_OUTPUT_DIR / article["downloadFileName"]
            try:
                shutil.move(str(temp_output_path), str(output_path))
                version = str(output_path.stat().st_mtime_ns)
            finally:
                temp_dir.cleanup()
        except VideoRenderRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return

        self.send_json(
            200,
            {
                "ok": True,
                "article_id": article["id"],
                "filename": article["downloadFileName"],
                "download_url": self.build_download_url(article["downloadFileName"], version),
            },
        )

    def handle_quiz_video_render_url(self) -> None:
        try:
            quiz, speaker = self.parse_quiz_video_request()
            VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            filename = quiz_video_filename(quiz["id"])
            output_path = VIDEO_OUTPUT_DIR / filename
            temp_dir = tempfile.TemporaryDirectory(prefix="learn-japanese-quiz-render-")
            temp_output_path = Path(temp_dir.name) / filename
            try:
                options = RenderOptions(article_id=quiz["id"], speaker=speaker)
                render_quiz_video(quiz, temp_output_path, options)
                shutil.move(str(temp_output_path), str(output_path))
                version = str(output_path.stat().st_mtime_ns)
            finally:
                temp_dir.cleanup()
        except VideoRenderRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return
        except SystemExit as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})
            return
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace").strip() if exc.stderr else str(exc)
            self.send_json(500, {"ok": False, "error": f"Quiz video render failed: {detail}"})
            return

        self.send_json(
            200,
            {
                "ok": True,
                "quiz_id": quiz["id"],
                "filename": filename,
                "download_url": self.build_download_url(filename, version),
            },
        )

    def parse_quiz_video_request(self) -> tuple[dict, int]:
        try:
            payload = self.read_json_body()
            quiz_id = str(payload.get("quiz_id", "")).strip()
            speaker_value = payload.get("speaker")
            speaker = int(speaker_value) if speaker_value is not None else DEFAULT_VOICEVOX_SPEAKER
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise VideoRenderRequestError(400, f"Invalid JSON request: {exc}") from exc

        if not quiz_id:
            raise VideoRenderRequestError(400, "Missing quiz_id.")

        try:
            return find_video_quiz(quiz_id), speaker
        except ValueError as exc:
            raise VideoRenderRequestError(404, str(exc)) from exc

    def render_video_to_temp_file(self) -> tuple[dict, Path, tempfile.TemporaryDirectory]:
        try:
            payload = self.read_json_body()
            article_id = str(payload.get("article_id", "")).strip()
            speaker_value = payload.get("speaker")
            speaker = int(speaker_value) if speaker_value is not None else DEFAULT_VOICEVOX_SPEAKER
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise VideoRenderRequestError(400, f"Invalid JSON request: {exc}") from exc

        if not article_id:
            raise VideoRenderRequestError(400, "Missing article_id.")

        try:
            article = find_article(article_id)
        except ValueError as exc:
            raise VideoRenderRequestError(404, str(exc)) from exc

        options = RenderOptions(article_id=article["id"], speaker=speaker)

        temp_dir = None
        try:
            temp_dir = tempfile.TemporaryDirectory(prefix="learn-japanese-render-")
            temp_path = Path(temp_dir.name)
            output_path = temp_path / article["downloadFileName"]
            render_article_video(article, output_path, options, DEFAULT_VOICEVOX_TIMEOUT)
            return article, output_path, temp_dir
        except SystemExit as exc:
            if temp_dir:
                temp_dir.cleanup()
            message = str(exc)
            status = 503 if "VOICEVOX" in message or "Chromium" in message or "ffmpeg" in message else 500
            raise VideoRenderRequestError(status, message) from exc
        except subprocess.CalledProcessError as exc:
            if temp_dir:
                temp_dir.cleanup()
            detail = exc.stderr.decode("utf-8", errors="replace").strip() if exc.stderr else str(exc)
            raise VideoRenderRequestError(500, f"Video render failed: {detail}") from exc

    def build_download_url(self, filename: str, version: str | None = None) -> str:
        host = self.headers.get("Host") or f"{DEFAULT_PUBLIC_HOST}:{DEFAULT_PORT}"
        proto = self.headers.get("X-Forwarded-Proto", "http").split(",", 1)[0].strip() or "http"
        url = f"{proto}://{host}/videos/{parse.quote(filename)}"
        if version:
            url = f"{url}?v={parse.quote(version)}"
        return url

    def read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        if not raw_body:
            return {}

        value = json.loads(raw_body.decode("utf-8"))
        if not isinstance(value, dict):
            raise TypeError("JSON body must be an object")

        return value

    def read_binary_body(self, max_bytes: int) -> bytes:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > max_bytes:
            raise ValueError(f"Video is too large. Limit is {max_bytes // (1024 * 1024)} MB.")

        return self.rfile.read(content_length)

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

class VideoRenderRequestError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def public_site_url(host: str, port: int) -> str:
    public_host = DEFAULT_PUBLIC_HOST if host in {"0.0.0.0", "::"} else host
    return f"http://{public_host}:{port}/index.html"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve static learn-japanese pages for browser-based study and recording."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), LearnJapaneseHandler)
    print(f"Open {public_site_url(args.host, args.port)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
