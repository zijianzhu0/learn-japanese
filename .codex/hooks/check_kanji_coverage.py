#!/usr/bin/env python3
"""Fail when changed article headline/body kanji appear outside ruby markup."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ARTICLE_DIR = Path("data/articles")
KANJI_RE = re.compile(r"[\u4e00-\u9fff]")
RUBY_RE = re.compile(r"<ruby>.*?<rt>.*?</rt></ruby>")


def git_paths(*args: str) -> list[Path]:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [Path(line) for line in result.stdout.splitlines() if line]


def changed_article_paths() -> list[Path]:
    changed = git_paths(
        "diff",
        "--name-only",
        "--diff-filter=ACMRT",
        "HEAD",
        "--",
        str(ARTICLE_DIR),
    )
    untracked = git_paths(
        "ls-files",
        "--others",
        "--exclude-standard",
        "--",
        str(ARTICLE_DIR),
    )
    return sorted({path for path in changed + untracked if path.suffix == ".json"})


def text_without_ruby(text: str) -> str:
    return RUBY_RE.sub("", text)


def coverage_failures(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = [("headlineHtml", data.get("headlineHtml", ""))]
    fields.extend(
        (f"paragraphs[{index}].html", paragraph.get("html", ""))
        for index, paragraph in enumerate(data.get("paragraphs", []))
    )

    failures = []
    for name, html in fields:
        uncovered = "".join(KANJI_RE.findall(text_without_ruby(html)))
        if uncovered:
            failures.append(f"{path}:{name}: uncovered kanji: {uncovered}")
    return failures


def main() -> int:
    failures: list[str] = []
    for path in changed_article_paths():
        if path.exists():
            failures.extend(coverage_failures(path))

    if failures:
        print("Kanji furigana coverage check failed.", file=sys.stderr)
        print("Wrap kanji in headlineHtml and paragraph html with <ruby>...</ruby>.", file=sys.stderr)
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
