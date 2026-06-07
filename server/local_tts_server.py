#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request


DEFAULT_HOST = os.environ.get("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT", "8765"))
DEFAULT_PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "127.0.0.1")
PROJECT_DIR = Path(__file__).resolve().parent.parent
VOICEVOX_BASE_URL = os.environ.get("VOICEVOX_BASE_URL", "http://127.0.0.1:50021")
DEFAULT_VOICEVOX_SPEAKER = 9
MAX_TTS_TEXT_CHARS = 500
MAX_VIDEO_UPLOAD_BYTES = 700 * 1024 * 1024


class LearnJapaneseHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/api/tts/voicevox/status":
            self.handle_voicevox_status()
            return

        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/tts/voicevox":
            self.handle_voicevox_synthesis()
            return

        if self.path == "/api/video/convert-mp4":
            self.handle_mp4_conversion()
            return

        self.send_json(404, {"ok": False, "error": "Unknown API endpoint."})

    def handle_voicevox_status(self) -> None:
        try:
            speakers = self.voicevox_request("GET", "/speakers")
        except VoicevoxError as exc:
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
            audio_query = self.voicevox_request(
                "POST",
                "/audio_query",
                query={"text": text, "speaker": speaker},
                body=b"",
            )
            wav_audio = self.voicevox_request(
                "POST",
                "/synthesis",
                query={"speaker": speaker},
                body=json.dumps(audio_query).encode("utf-8"),
                content_type="application/json",
                expect_json=False,
            )
        except VoicevoxError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return

        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(wav_audio)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(wav_audio)

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

    def voicevox_request(
        self,
        method: str,
        endpoint: str,
        *,
        query: dict | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
        expect_json: bool = True,
    ):
        query_string = f"?{parse.urlencode(query)}" if query else ""
        url = f"{VOICEVOX_BASE_URL}{endpoint}{query_string}"
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        api_request = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(api_request, timeout=30) as response:
                response_body = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise VoicevoxError(exc.code, f"VOICEVOX returned {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise VoicevoxError(
                503,
                f"VOICEVOX is not reachable at {VOICEVOX_BASE_URL}. Start it with docker compose up voicevox.",
            ) from exc

        if not expect_json:
            return response_body

        return json.loads(response_body.decode("utf-8"))


class VoicevoxError(Exception):
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
