#!/usr/bin/env python3

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib import parse

from render_video import (
    DEFAULT_SPEAKER,
    DEFAULT_VOICEVOX_TIMEOUT,
    ROOT,
    RenderOptions,
    find_article,
    render_article_video,
)


DEFAULT_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8765")
DEFAULT_URL_PATH = "/videos"


def download_url(base_url: str, url_path: str, filename: str, version: str | None = None) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = f"/{url_path.strip('/')}" if url_path else ""
    url = f"{normalized_base}{normalized_path}/{parse.quote(filename)}"
    if version:
        url = f"{url}?v={parse.quote(version)}"
    return url


def render_to_output_dir(
    article: dict,
    output_dir: Path,
    options: RenderOptions,
    voicevox_timeout: float,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / article["downloadFileName"]

    with tempfile.TemporaryDirectory(prefix="learn-japanese-render-url-") as temp_dir:
        temp_output_path = Path(temp_dir) / article["downloadFileName"]
        render_article_video(article, temp_output_path, options, voicevox_timeout)
        temp_output_path.replace(output_path)

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render an article MP4 into a served directory and print a JSON download URL."
    )
    parser.add_argument("article", help="Article id, slug, or generated HTML filename.")
    parser.add_argument("--speaker", type=int, default=DEFAULT_SPEAKER)
    parser.add_argument("--voicevox-timeout", type=float, default=DEFAULT_VOICEVOX_TIMEOUT)
    parser.add_argument("--output-dir", default=str(ROOT / "videos"))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--url-path", default=DEFAULT_URL_PATH)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON response.")
    args = parser.parse_args()

    try:
        article = find_article(args.article)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    options = RenderOptions(article_id=article["id"], speaker=args.speaker)
    with contextlib.redirect_stdout(sys.stderr):
        output_path = render_to_output_dir(article, output_dir, options, args.voicevox_timeout)

    payload = {
        "ok": True,
        "article_id": article["id"],
        "filename": output_path.name,
        "path": str(output_path),
        "download_url": download_url(
            args.base_url,
            args.url_path,
            output_path.name,
            str(output_path.stat().st_mtime_ns),
        ),
    }
    indent = 2 if args.pretty else None
    print(json.dumps(payload, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()
