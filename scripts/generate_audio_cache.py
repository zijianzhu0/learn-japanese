#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_site import FLASHCARDS_PATH
from scripts.render_video import build_segments, load_articles
from scripts.voicevox_cache import (
    DEFAULT_AUDIO_CACHE_DIR,
    DEFAULT_VOICEVOX_BASE_URL,
    VoicevoxRequestError,
    cache_path,
    cached_voicevox_wav,
    voicevox_request,
)


def article_audio_targets() -> list[tuple[str, str]]:
    targets = []
    for article in load_articles():
        for segment in build_segments(article):
            targets.append((f"article:{article['id']}:{segment.key}", segment.text))
    return targets


def flashcard_audio_targets() -> list[tuple[str, str]]:
    payload = json.loads(FLASHCARDS_PATH.read_text(encoding="utf-8"))
    targets = []
    for item in payload.get("items", []):
        item_id = str(item.get("id", ""))
        term = str(item.get("term", "")).strip()
        if term:
            targets.append((f"flashcard:{item_id}:term", term))
        for index, example in enumerate(item.get("exampleSentences", []), start=1):
            text = str(example.get("ja", "")).strip()
            if text:
                targets.append((f"flashcard:{item_id}:example:{index}", text))
    return targets


def unique_targets(targets: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    unique = []
    for label, text in targets:
        if text in seen:
            continue
        seen.add(text)
        unique.append((label, text))
    return unique


def selected_targets(include_articles: bool, include_flashcards: bool) -> list[tuple[str, str]]:
    targets = []
    if include_articles:
        targets.extend(article_audio_targets())
    if include_flashcards:
        targets.extend(flashcard_audio_targets())
    return unique_targets(targets)


def wait_for_voicevox(base_url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            voicevox_request("GET", "/speakers", base_url=base_url)
            return
        except VoicevoxRequestError as exc:
            last_error = exc.message
            time.sleep(1)
    raise SystemExit(f"VOICEVOX is not reachable at {base_url}: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-generate cached VOICEVOX WAV audio for articles and flashcards.")
    parser.add_argument("--articles", action="store_true", help="Generate article title and sentence audio.")
    parser.add_argument("--flashcards", action="store_true", help="Generate flashcard term and example audio.")
    parser.add_argument("--speaker", type=int, default=9)
    parser.add_argument("--voicevox-base-url", default=DEFAULT_VOICEVOX_BASE_URL)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_AUDIO_CACHE_DIR)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--limit", type=int, default=0, help="Generate at most this many uncached targets.")
    parser.add_argument("--force", action="store_true", help="Regenerate audio even when a cache file already exists.")
    parser.add_argument("--dry-run", action="store_true", help="Report target counts without contacting VOICEVOX.")
    args = parser.parse_args()

    include_articles = args.articles or not args.flashcards
    include_flashcards = args.flashcards or not args.articles
    targets = selected_targets(include_articles, include_flashcards)
    uncached = [
        (label, text)
        for label, text in targets
        if args.force or not cache_path(text, args.speaker, cache_dir=args.cache_dir).exists()
    ]
    if args.limit > 0:
        uncached = uncached[: args.limit]

    print(
        json.dumps(
            {
                "speaker": args.speaker,
                "cacheDir": str(args.cache_dir),
                "targets": len(targets),
                "uncached": len(uncached),
                "articles": include_articles,
                "flashcards": include_flashcards,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if args.dry_run or not uncached:
        return

    wait_for_voicevox(args.voicevox_base_url, args.timeout)
    for index, (label, text) in enumerate(uncached, start=1):
        print(f"[{index}/{len(uncached)}] {label}: {text}", flush=True)
        cached_voicevox_wav(
            text,
            args.speaker,
            base_url=args.voicevox_base_url,
            cache_dir=args.cache_dir,
            timeout=args.timeout,
            force=args.force,
        )


if __name__ == "__main__":
    main()
