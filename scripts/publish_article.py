#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import error, request


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish an article JSON file to the local runtime article API."
    )
    parser.add_argument("article_json", type=Path, help="Path to an article JSON file.")
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8765",
        help="Base server URL. Default: http://127.0.0.1:8765",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing runtime article with the same id or file.",
    )
    args = parser.parse_args()

    article = json.loads(args.article_json.read_text(encoding="utf-8"))
    payload = json.dumps(
        {"article": article, "overwrite": args.overwrite},
        ensure_ascii=False,
    ).encode("utf-8")
    endpoint = args.server.rstrip("/") + "/api/articles"
    req = request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with request.urlopen(req) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Publish failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Publish failed: {exc}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        print(body)
        return

    print(json.dumps(parsed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
