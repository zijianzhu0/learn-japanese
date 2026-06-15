#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import tempfile
from hashlib import sha256
from pathlib import Path
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VOICEVOX_BASE_URL = os.environ.get("VOICEVOX_BASE_URL", "http://127.0.0.1:50021")
DEFAULT_AUDIO_CACHE_DIR = Path(os.environ.get("AUDIO_CACHE_DIR", ROOT / ".generated_audio" / "voicevox"))
DEFAULT_TIMEOUT = 30
CACHE_VERSION = "voicevox-wav-v1"


class VoicevoxRequestError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def cache_key(text: str, speaker: int, *, trailing_silence: float | None = None) -> str:
    payload = {
        "version": CACHE_VERSION,
        "engine": "VOICEVOX",
        "speaker": speaker,
        "text": text,
        "trailing_silence": trailing_silence,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def cache_path(
    text: str,
    speaker: int,
    *,
    trailing_silence: float | None = None,
    cache_dir: Path = DEFAULT_AUDIO_CACHE_DIR,
) -> Path:
    key = cache_key(text, speaker, trailing_silence=trailing_silence)
    return cache_dir / str(speaker) / f"{key}.wav"


def voicevox_request(
    method: str,
    endpoint: str,
    *,
    base_url: str = DEFAULT_VOICEVOX_BASE_URL,
    query: dict | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
    expect_json: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
):
    query_string = f"?{parse.urlencode(query)}" if query else ""
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    api_request = request.Request(
        f"{base_url}{endpoint}{query_string}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with request.urlopen(api_request, timeout=timeout) as response:
            response_body = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise VoicevoxRequestError(exc.code, f"VOICEVOX returned {exc.code}: {detail}") from exc
    except (error.URLError, TimeoutError) as exc:
        raise VoicevoxRequestError(
            503,
            f"VOICEVOX is not reachable at {base_url}. Start it with docker compose up voicevox.",
        ) from exc

    if not expect_json:
        return response_body

    try:
        return json.loads(response_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise VoicevoxRequestError(502, f"VOICEVOX returned invalid JSON: {exc}") from exc


def synthesize_voicevox_wav(
    text: str,
    speaker: int,
    *,
    base_url: str = DEFAULT_VOICEVOX_BASE_URL,
    trailing_silence: float | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> bytes:
    audio_query = voicevox_request(
        "POST",
        "/audio_query",
        base_url=base_url,
        query={"text": text, "speaker": speaker},
        body=b"",
        timeout=timeout,
    )
    if trailing_silence is not None:
        audio_query["postPhonemeLength"] = trailing_silence
    return voicevox_request(
        "POST",
        "/synthesis",
        base_url=base_url,
        query={"speaker": speaker},
        body=json.dumps(audio_query).encode("utf-8"),
        content_type="application/json",
        expect_json=False,
        timeout=timeout,
    )


def cached_voicevox_wav(
    text: str,
    speaker: int,
    *,
    base_url: str = DEFAULT_VOICEVOX_BASE_URL,
    trailing_silence: float | None = None,
    cache_dir: Path = DEFAULT_AUDIO_CACHE_DIR,
    timeout: float = DEFAULT_TIMEOUT,
    force: bool = False,
) -> tuple[bytes, bool, Path]:
    path = cache_path(text, speaker, trailing_silence=trailing_silence, cache_dir=cache_dir)
    if path.exists() and not force:
        return path.read_bytes(), True, path

    wav_audio = synthesize_voicevox_wav(
        text,
        speaker,
        base_url=base_url,
        trailing_silence=trailing_silence,
        timeout=timeout,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent, delete=False) as temp_file:
        temp_file.write(wav_audio)
        temp_path = Path(temp_file.name)
    temp_path.replace(path)
    return wav_audio, False, path
