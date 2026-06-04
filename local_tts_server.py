#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PROJECT_DIR = Path(__file__).resolve().parent
VOICEVOX_BASE_URL = "http://127.0.0.1:50021"
DEFAULT_VOICEVOX_SPEAKER = 3
MAX_TTS_TEXT_CHARS = 500


class LearnJapaneseHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/tts/voicevox/status":
            self.handle_voicevox_status()
            return

        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/tts/voicevox":
            self.handle_voicevox_synthesis()
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

    def read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        if not raw_body:
            return {}

        value = json.loads(raw_body.decode("utf-8"))
        if not isinstance(value, dict):
            raise TypeError("JSON body must be an object")

        return value

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve static learn-japanese pages for browser-based study and recording."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), LearnJapaneseHandler)
    print(f"Serving {PROJECT_DIR} at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
