#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass
from hashlib import sha1
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parent.parent
ARTICLES_MANIFEST = ROOT / "data" / "articles.json"
FLASHCARDS_MANIFEST = ROOT / "data" / "flashcards.json"
ARTICLE_CSS = ROOT / "assets" / "article.css"
IG_VIDEOS_CSS = ROOT / "assets" / "ig-videos.css"
VOICEVOX_BASE_URL = os.environ.get("VOICEVOX_BASE_URL", "http://127.0.0.1:50021")
DEFAULT_SPEAKER = int(os.environ.get("VOICEVOX_SPEAKER", "9"))
FRAME_WIDTH = 1080
FRAME_HEIGHT = 1920
FRAME_RATE = 30
MIN_SEGMENT_SECONDS = 0.8
TRAILING_SILENCE_SECONDS = 0.25
DEFAULT_VOICEVOX_TIMEOUT = 90


@dataclass(frozen=True)
class RenderOptions:
    article_id: str
    speaker: int = DEFAULT_SPEAKER
    frame_width: int = FRAME_WIDTH
    frame_height: int = FRAME_HEIGHT
    frame_rate: int = FRAME_RATE


@dataclass
class Segment:
    key: str
    text: str
    title_html: str
    paragraph_htmls: list[str]


@dataclass
class VocabSegment:
    key: str
    text: str
    active_index: int


class BaseTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"rt", "rp"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"rt", "rp"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self.parts)).strip()


def html_base_text(html: str) -> str:
    parser = BaseTextParser()
    parser.feed(html)
    return parser.text()


def split_plain_sentences(text: str) -> list[str]:
    matches = re.findall(r"[^。！？!?]+[。！？!?]?", text)
    return [match.strip() for match in matches if match.strip()]


def split_html_sentences(html: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(html):
        char = html[index]
        if char == "<":
            end = html.find(">", index)
            if end == -1:
                break
            tag = html[index + 1 : end].strip()
            if tag.startswith("ruby"):
                depth += 1
            elif tag.startswith("/ruby") and depth:
                depth -= 1
            index = end + 1
            continue
        if depth == 0 and char in "。！？!?":
            pieces.append(html[start : index + 1].strip())
            start = index + 1
        index += 1
    tail = html[start:].strip()
    if tail:
        pieces.append(tail)
    return pieces or [html]


def load_articles() -> list[dict]:
    manifest = json.loads(ARTICLES_MANIFEST.read_text(encoding="utf-8"))
    articles = []
    for article_path in manifest["articles"]:
        path = ARTICLES_MANIFEST.parent / article_path
        articles.append(json.loads(path.read_text(encoding="utf-8")))
    return articles


def find_article(article_ref: str) -> dict:
    normalized = article_ref.removesuffix(".json").removesuffix(".html")
    for article in load_articles():
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", article["id"])
        candidates = {
            article["id"],
            slug,
            article["file"],
            article["file"].removesuffix(".html"),
            Path(article["file"]).stem,
        }
        if article_ref in candidates or normalized in candidates:
            return article
    raise ValueError(f"Article not found: {article_ref}")


def load_flashcard_items() -> list[dict]:
    manifest = json.loads(FLASHCARDS_MANIFEST.read_text(encoding="utf-8"))
    return list(manifest.get("items", []))


def find_vocab_items(item_ids: list[str]) -> list[dict]:
    items_by_id = {item["id"]: item for item in load_flashcard_items()}
    selected = []
    missing = []
    for item_id in item_ids:
        item = items_by_id.get(item_id)
        if item:
            selected.append(item)
        else:
            missing.append(item_id)
    if missing:
        raise ValueError(f"Vocabulary item not found: {', '.join(missing)}")
    if len(selected) != 5:
        raise ValueError("Vocabulary videos require exactly five items.")
    return selected


def highlighted(html: str, active: bool) -> str:
    class_name = "reading-unit is-speaking" if active else "reading-unit"
    return f'<span class="{class_name}">{html}</span>'


def build_segments(article: dict) -> list[Segment]:
    title_sentences = split_plain_sentences(html_base_text(article["headlineHtml"]))
    title_text = " ".join(title_sentences) or html_base_text(article["headlineHtml"])
    segments = [
        Segment(
            key="title",
            text=title_text,
            title_html=highlighted(article["headlineHtml"], True),
            paragraph_htmls=[paragraph["html"] for paragraph in article["paragraphs"]],
        )
    ]

    for paragraph_index, paragraph in enumerate(article["paragraphs"]):
        sentence_htmls = split_html_sentences(paragraph["html"])
        for sentence_index, sentence_html in enumerate(sentence_htmls):
            rendered_paragraphs = []
            for current_index, current_paragraph in enumerate(article["paragraphs"]):
                if current_index != paragraph_index:
                    rendered_paragraphs.append(current_paragraph["html"])
                    continue
                rendered_paragraphs.append(
                    "".join(
                        highlighted(item, item_index == sentence_index)
                        for item_index, item in enumerate(sentence_htmls)
                    )
                )
            segments.append(
                Segment(
                    key=f"p{paragraph_index + 1}-{sentence_index + 1}",
                    text=html_base_text(sentence_html),
                    title_html=article["headlineHtml"],
                    paragraph_htmls=rendered_paragraphs,
                )
            )
    return segments


def vocab_term(item: dict) -> str:
    return str(item.get("term", "")).split("/")[0].strip()


def vocab_reading(item: dict) -> str:
    return str(item.get("readingHiragana") or item.get("reading") or "").split("/")[0].strip()


def vocab_meaning(item: dict) -> str:
    return str(item.get("meaning") or "").split(";")[0].strip()


def vocab_ruby_html(item: dict) -> str:
    term = vocab_term(item)
    reading = vocab_reading(item)
    if not reading or reading == term:
        return escape(term)
    return f"<ruby>{escape(term)}<rt>{escape(reading)}</rt></ruby>"


def build_vocab_segments(items: list[dict]) -> list[VocabSegment]:
    return [
        VocabSegment(
            key=f"word-{index + 1}",
            text=vocab_term(item),
            active_index=index,
        )
        for index, item in enumerate(items)
    ]


def voicevox_request(
    method: str,
    endpoint: str,
    *,
    query: dict | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
    expect_json: bool = True,
):
    query_string = f"?{parse.urlencode(query)}" if query else ""
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    api_request = request.Request(
        f"{VOICEVOX_BASE_URL}{endpoint}{query_string}",
        data=body,
        headers=headers,
        method=method,
    )
    with request.urlopen(api_request, timeout=60) as response:
        response_body = response.read()
    if not expect_json:
        return response_body
    return json.loads(response_body.decode("utf-8"))


def wait_for_voicevox(timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            voicevox_request("GET", "/speakers")
            return
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            time.sleep(1)
    raise SystemExit(f"VOICEVOX is not reachable at {VOICEVOX_BASE_URL}: {last_error}")


def synthesize_sentence(text: str, speaker: int) -> bytes:
    audio_query = voicevox_request(
        "POST",
        "/audio_query",
        query={"text": text, "speaker": speaker},
        body=b"",
    )
    audio_query["postPhonemeLength"] = TRAILING_SILENCE_SECONDS
    return voicevox_request(
        "POST",
        "/synthesis",
        query={"speaker": speaker},
        body=json.dumps(audio_query).encode("utf-8"),
        content_type="application/json",
        expect_json=False,
    )


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
    return frames / float(rate)


def render_html(article: dict, segment: Segment, options: RenderOptions) -> str:
    css = ARTICLE_CSS.read_text(encoding="utf-8")
    paragraphs = "\n".join(
        f'        <p class="article-paragraph">{paragraph_html}</p>'
        for paragraph_html in segment.paragraph_htmls
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <style>{css}</style>
    <style>
        html, body {{
            width: {options.frame_width}px;
            height: {options.frame_height}px;
        }}
        body {{
            --recording-frame-width: {options.frame_width}px;
            --recording-frame-height: {options.frame_height}px;
            max-width: none;
            font-family: "Noto Sans CJK JP", "Noto Sans JP", sans-serif;
        }}
    </style>
</head>
<body class="recording-mode recording-export">
<div class="article-shell">
    <main class="article-main">
        <div class="container">
            <div class="date">{escape(article["date"])}</div>
            <h1>{segment.title_html}</h1>
{paragraphs}
        </div>
    </main>
</div>
<script>
function fitRecordingPageText() {{
    const frame = document.querySelector('.article-main');
    const container = document.querySelector('.container');
    if (!frame || !container) {{
        return;
    }}
    document.body.style.removeProperty('--recording-title-size');
    document.body.style.removeProperty('--recording-body-size');
    document.body.style.removeProperty('--recording-body-line-height');
    const pageWidth = frame.clientWidth || container.clientWidth;
    let bodySize = Math.max(22, Math.min(58, pageWidth * 0.035));
    let titleSize = bodySize * 1.32;
    let lineHeight = 1.68;
    const applySizes = () => {{
        document.body.style.setProperty('--recording-title-size', `${{titleSize}}px`);
        document.body.style.setProperty('--recording-body-size', `${{bodySize}}px`);
        document.body.style.setProperty('--recording-body-line-height', String(lineHeight));
    }};
    applySizes();
    while (container.scrollHeight > container.clientHeight && bodySize > 12) {{
        bodySize -= 1;
        titleSize = bodySize * 1.32;
        if (bodySize < 18) {{
            lineHeight = 1.48;
        }} else if (bodySize < 22) {{
            lineHeight = 1.56;
        }}
        applySizes();
    }}
}}
window.addEventListener('load', fitRecordingPageText);
</script>
</body>
</html>
"""


def render_vocab_html(items: list[dict], segment: VocabSegment, options: RenderOptions) -> str:
    css = IG_VIDEOS_CSS.read_text(encoding="utf-8")
    levels = sorted({str(item.get("level", "")) for item in items if item.get("level")})
    level_label = "Mixed JLPT" if len(levels) != 1 else levels[0]
    words_html = "\n".join(
        f"""                    <li class="word-card{' is-speaking' if index == segment.active_index else ''}">
                        <span class="word-index">{index + 1}</span>
                        <span class="word-main">
                            <span class="word-term">{vocab_ruby_html(item)}</span>
                            <span class="word-meaning">{escape(vocab_meaning(item))}</span>
                        </span>
                        <span class="level-pill">{escape(str(item.get("level", "")))}</span>
                    </li>"""
        for index, item in enumerate(items)
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <style>{css}</style>
    <style>
        html, body {{
            width: {options.frame_width}px;
            height: {options.frame_height}px;
            margin: 0;
            background: #121820;
        }}
        body {{
            display: block;
            overflow: hidden;
        }}
        .top-nav,
        .control-panel {{
            display: none;
        }}
        .video-workspace {{
            display: block;
            width: {options.frame_width}px;
            margin: 0;
        }}
        .preview-column {{
            display: block;
        }}
        .phone-frame {{
            width: {options.frame_width}px;
            height: {options.frame_height}px;
            padding: 0;
            border-radius: 0;
            box-shadow: none;
            background: #121820;
        }}
        .ig-stage {{
            width: {options.frame_width}px;
            height: {options.frame_height}px;
            border-radius: 0;
        }}
        .stage-kicker,
        .stage-meta,
        .stage-footer {{
            font-size: 34px;
        }}
        .stage-header h1 {{
            font-size: 76px;
        }}
        .word-card {{
            gap: 28px;
            padding: 26px 30px;
            border-radius: 18px;
        }}
        .word-index {{
            width: 72px;
            height: 72px;
            font-size: 28px;
        }}
        .word-term {{
            font-size: 68px;
        }}
        .word-meaning {{
            font-size: 32px;
        }}
        .level-pill {{
            padding: 10px 16px;
            font-size: 26px;
        }}
    </style>
</head>
<body>
<main class="video-workspace">
    <section class="preview-column" aria-label="IG video preview">
        <div class="phone-frame">
            <article class="ig-stage">
                <header class="stage-header">
                    <span class="stage-kicker">日本語 Vocabulary</span>
                    <h1>{escape(level_label)} · 5 words</h1>
                    <span class="stage-meta">9:16 · 1080x1920</span>
                </header>
                <ol class="word-list">
{words_html}
                </ol>
                <footer class="stage-footer">
                    <span>Read. Listen. Repeat.</span>
                    <span>{segment.active_index + 1}/5</span>
                </footer>
            </article>
        </div>
    </section>
</main>
</body>
</html>
"""


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def chromium_command() -> str:
    configured_path = os.environ.get("CHROMIUM_PATH")
    if configured_path and Path(configured_path).exists():
        return configured_path

    for candidate in ("chromium", "chromium-browser", "google-chrome"):
        path = shutil.which(candidate)
        if path:
            return path
    for candidate in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
        if Path(candidate).exists():
            return candidate
    raise SystemExit("Chromium is required for CLI video rendering.")


def render_screenshot(chromium: str, html_path: Path, output_path: Path, options: RenderOptions) -> None:
    run(
        [
            chromium,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            f"--window-size={options.frame_width},{options.frame_height}",
            "--virtual-time-budget=1000",
            f"--screenshot={output_path}",
            html_path.as_uri(),
        ]
    )


def render_segment_video(
    image_path: Path,
    audio_path: Path,
    duration: float,
    output_path: Path,
    options: RenderOptions,
) -> None:
    rounded_duration = max(MIN_SEGMENT_SECONDS, math.ceil(duration * options.frame_rate) / options.frame_rate)
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            str(options.frame_rate),
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
            "-t",
            f"{rounded_duration:.3f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            str(output_path),
        ]
    )


def concatenate_segments(segment_paths: list[Path], concat_path: Path, output_path: Path) -> None:
    concat_path.write_text(
        "\n".join(f"file '{path.as_posix()}'" for path in segment_paths),
        encoding="utf-8",
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def render_article_video(
    article: dict,
    output_path: Path,
    options: RenderOptions,
    voicevox_timeout: float = DEFAULT_VOICEVOX_TIMEOUT,
) -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required for CLI video rendering.")

    wait_for_voicevox(voicevox_timeout)
    segments = build_segments(article)
    chromium = chromium_command()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="learn-japanese-render-") as temp_dir:
        temp_path = Path(temp_dir)
        segment_paths = []
        for index, segment in enumerate(segments, start=1):
            print(f"[{index}/{len(segments)}] {segment.text}", flush=True)
            html_path = temp_path / f"{index:03d}-{segment.key}.html"
            image_path = temp_path / f"{index:03d}-{segment.key}.png"
            audio_path = temp_path / f"{index:03d}-{segment.key}.wav"
            video_path = temp_path / f"{index:03d}-{segment.key}.mp4"

            html_path.write_text(render_html(article, segment, options), encoding="utf-8")
            audio_path.write_bytes(synthesize_sentence(segment.text, options.speaker))
            render_screenshot(chromium, html_path, image_path, options)
            render_segment_video(image_path, audio_path, wav_duration(audio_path), video_path, options)
            segment_paths.append(video_path)

        concatenate_segments(segment_paths, temp_path / "segments.txt", output_path)


def render_vocab_video(
    items: list[dict],
    output_path: Path,
    options: RenderOptions,
    voicevox_timeout: float = DEFAULT_VOICEVOX_TIMEOUT,
) -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required for CLI video rendering.")

    wait_for_voicevox(voicevox_timeout)
    segments = build_vocab_segments(items)
    chromium = chromium_command()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="learn-japanese-vocab-render-") as temp_dir:
        temp_path = Path(temp_dir)
        segment_paths = []
        for index, segment in enumerate(segments, start=1):
            print(f"[{index}/{len(segments)}] {segment.text}", flush=True)
            html_path = temp_path / f"{index:03d}-{segment.key}.html"
            image_path = temp_path / f"{index:03d}-{segment.key}.png"
            audio_path = temp_path / f"{index:03d}-{segment.key}.wav"
            video_path = temp_path / f"{index:03d}-{segment.key}.mp4"

            html_path.write_text(render_vocab_html(items, segment, options), encoding="utf-8")
            audio_path.write_bytes(synthesize_sentence(segment.text, options.speaker))
            render_screenshot(chromium, html_path, image_path, options)
            render_segment_video(image_path, audio_path, wav_duration(audio_path), video_path, options)
            segment_paths.append(video_path)

        concatenate_segments(segment_paths, temp_path / "segments.txt", output_path)


def vocab_video_filename(item_ids: list[str]) -> str:
    digest = sha1("\n".join(item_ids).encode("utf-8")).hexdigest()[:10]
    return f"ig-vocabulary-{digest}.mp4"


def render_video(article: dict, output_path: Path, speaker: int, voicevox_timeout: float) -> None:
    options = RenderOptions(article_id=article["id"], speaker=speaker)
    render_article_video(article, output_path, options, voicevox_timeout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render an article MP4 from JSON, CSS, VOICEVOX audio, Chromium screenshots, and ffmpeg."
    )
    parser.add_argument("article", help="Article id, slug, or generated HTML filename.")
    parser.add_argument("-o", "--output", help="Output MP4 path. Defaults to the article downloadFileName.")
    parser.add_argument("--speaker", type=int, default=DEFAULT_SPEAKER)
    parser.add_argument("--voicevox-timeout", type=float, default=DEFAULT_VOICEVOX_TIMEOUT)
    args = parser.parse_args()

    try:
        article = find_article(args.article)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    output_path = Path(args.output or article["downloadFileName"])
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    options = RenderOptions(article_id=article["id"], speaker=args.speaker)
    render_article_video(article, output_path, options, args.voicevox_timeout)
    print(f"Rendered {output_path}", flush=True)


if __name__ == "__main__":
    main()
