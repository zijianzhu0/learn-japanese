#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib import error

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.voicevox_cache import (
    DEFAULT_VOICEVOX_BASE_URL,
    VoicevoxRequestError,
    cached_voicevox_wav,
    voicevox_request,
)


ARTICLES_MANIFEST = ROOT / "data" / "articles.json"
VIDEO_QUIZZES_MANIFEST = ROOT / "data" / "video-quizzes.json"
ARTICLE_CSS = ROOT / "assets" / "article.css"
IG_VIDEOS_CSS = ROOT / "assets" / "ig-videos.css"
VOICEVOX_BASE_URL = DEFAULT_VOICEVOX_BASE_URL
DEFAULT_SPEAKER = int(os.environ.get("VOICEVOX_SPEAKER", "9"))
FRAME_WIDTH = 1080
FRAME_HEIGHT = 1920
FRAME_RATE = 30
MIN_SEGMENT_SECONDS = 0.8
TRAILING_SILENCE_SECONDS = 0.25
DEFAULT_VOICEVOX_TIMEOUT = 90
EXPORT_AUDIO_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"


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


def load_video_quizzes() -> list[dict]:
    manifest = json.loads(VIDEO_QUIZZES_MANIFEST.read_text(encoding="utf-8"))
    return list(manifest.get("quizzes", []))


def find_video_quiz(quiz_id: str) -> dict:
    for quiz in load_video_quizzes():
        if quiz.get("id") == quiz_id:
            return quiz
    raise ValueError(f"Quiz not found: {quiz_id}")


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


def wait_for_voicevox(timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            voicevox_request("GET", "/speakers", base_url=VOICEVOX_BASE_URL, timeout=60)
            return
        except (VoicevoxRequestError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            time.sleep(1)
    raise SystemExit(f"VOICEVOX is not reachable at {VOICEVOX_BASE_URL}: {last_error}")


def cached_sentence_audio_path(text: str, speaker: int) -> Path:
    _, _, audio_path = cached_voicevox_wav(
        text,
        speaker,
        base_url=VOICEVOX_BASE_URL,
        timeout=60,
    )
    return audio_path


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
            <div class="recording-footer" aria-hidden="true">
                <span>英訳はコメント欄にあります</span>
                <span>{escape(article["date"])}</span>
            </div>
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


def render_quiz_html(quiz: dict, options: RenderOptions) -> str:
    css = IG_VIDEOS_CSS.read_text(encoding="utf-8")
    option_html = "\n".join(
        f"""                    <li class="option-card">
                        <span class="option-letter">{chr(65 + index)}</span>
                        <span class="option-text">{escape(str(option.get("label", "")))}</span>
                    </li>"""
        for index, option in enumerate(quiz.get("options", []))
    )
    level = str(quiz.get("level", ""))
    meta = f"{level} · 選択問題" if level else "選択問題"
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
        .quiz-workspace {{
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
        .quiz-stage {{
            width: {options.frame_width}px;
            height: {options.frame_height}px;
            border-radius: 0;
            padding: 170px 110px 145px;
        }}
        .stage-kicker,
        .stage-meta,
        .stage-footer {{
            font-size: 34px;
        }}
        .stage-header h1 {{
            font-size: 68px;
        }}
        .question-block {{
            min-height: 250px;
            margin: 34px 0;
            padding: 30px 34px;
            border-radius: 18px;
        }}
        .question-block p {{
            font-size: 48px;
        }}
        .option-list {{
            gap: 24px;
            margin-bottom: 34px;
        }}
        .option-card {{
            gap: 24px;
            padding: 26px 30px;
            border-radius: 18px;
        }}
        .option-letter {{
            width: 76px;
            height: 76px;
            font-size: 30px;
        }}
        .option-text {{
            font-size: 40px;
        }}
    </style>
</head>
<body>
<main class="quiz-workspace">
    <section class="preview-column" aria-label="Quiz video preview">
        <div class="phone-frame">
            <article class="quiz-stage">
                <header class="stage-header">
                    <span class="stage-kicker">{escape(str(quiz.get("kicker", "Japanese Reading Quiz")))}</span>
                    <h1>{escape(str(quiz.get("title", "")))}</h1>
                    <span class="stage-meta">{escape(meta)}</span>
                </header>
                <section class="question-block">
                    <p>{escape(str(quiz.get("question", "")))}</p>
                </section>
                <ol class="option-list">
{option_html}
                </ol>
                <footer class="stage-footer">
                    <span>{escape(str(quiz.get("footerLeft", "全文はコメントへ")))}</span>
                    <span>{escape(str(quiz.get("footerRight", "Choose A-D")))}</span>
                </footer>
            </article>
        </div>
    </section>
</main>
</body>
</html>
"""


def render_article_cover_html(article: dict, options: RenderOptions) -> str:
    cover_kicker = "Japanese Reading Exercise"
    title_translation = str(article.get("titleTranslation", "")).strip()
    emoji_pool = [
        "☆",
        "★",
        "♡",
        "♥",
        "❤",
        "✿",
        "✦",
        "✧",
        "✱",
        "✲",
        "✸",
        "❁",
        "❀",
        "☁",
        "♫",
        "☾",
        "☼",
        "∞",
        "○",
        "●",
        "◎",
        "◇",
        "◆",
    ]
    randomizer = random.SystemRandom()
    shuffled_emojis = emoji_pool[:]
    randomizer.shuffle(shuffled_emojis)

    def next_emoji() -> str:
        nonlocal shuffled_emojis
        if not shuffled_emojis:
            shuffled_emojis = emoji_pool[:]
            randomizer.shuffle(shuffled_emojis)
        return shuffled_emojis.pop()

    emoji_count = randomizer.randint(12, 18)
    emoji_specs = []
    occupied_positions: list[tuple[int, int, float]] = []
    attempts = 0
    while len(emoji_specs) < emoji_count and attempts < 600:
        attempts += 1
        size_px = randomizer.randint(54, 132)
        left = randomizer.randint(2, 92)
        top = randomizer.randint(2, 94)
        if 20 <= left <= 80 and 18 <= top <= 86:
            continue
        spacing_radius = max(8.0, min(17.0, size_px / 10.0))
        if any(
            math.hypot(left - existing_left, top - existing_top)
            < spacing_radius + existing_radius
            for existing_left, existing_top, existing_radius in occupied_positions
        ):
            continue
        occupied_positions.append((left, top, spacing_radius))
        emoji_specs.append(
            (
                next_emoji(),
                f"{left}%",
                f"{top}%",
                f"{size_px}px",
                f"{randomizer.randint(-24, 24)}deg",
                round(randomizer.uniform(0.06, 0.16), 2),
            )
        )
    kicker_html = f'        <p class="cover-kicker">{escape(cover_kicker)}</p>'
    translation_html = (
        f'        <p class="cover-translation">{escape(title_translation)}</p>'
        if title_translation
        else ""
    )
    emoji_texture_html = "\n".join(
        '        <span style="left: {left}; top: {top}; --emoji-size: {size}; --emoji-rotate: {rotate}; --emoji-opacity: {opacity};">{emoji}</span>'.format(
            left=left,
            top=top,
            size=size,
            rotate=rotate,
            opacity=opacity,
            emoji=escape(emoji),
        )
        for emoji, left, top, size, rotate, opacity in emoji_specs
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <style>
        * {{
            box-sizing: border-box;
        }}
        html,
        body {{
            width: {options.frame_width}px;
            height: {options.frame_height}px;
            margin: 0;
        }}
        body {{
            display: grid;
            place-items: center;
            padding: 96px;
            position: relative;
            overflow: hidden;
            color: #333;
            background:
                radial-gradient(circle at top left, #f2f2f2, transparent 34%),
                radial-gradient(circle at bottom right, #ececec, transparent 28%),
                linear-gradient(180deg, #fafafa 0%, #f3f3f3 100%);
            font-family: "Noto Sans CJK JP", "Noto Sans JP", "Helvetica Neue", Arial, sans-serif;
        }}
        .emoji-texture {{
            position: absolute;
            inset: 0;
            overflow: hidden;
            pointer-events: none;
            z-index: 0;
        }}
        .emoji-texture span {{
            position: absolute;
            display: block;
            color: #8f8f8f;
            font-size: var(--emoji-size);
            line-height: 1;
            opacity: var(--emoji-opacity);
            filter: grayscale(1) saturate(0) contrast(0.9);
            transform: rotate(var(--emoji-rotate));
            user-select: none;
            white-space: nowrap;
        }}
        .cover-card {{
            position: relative;
            z-index: 1;
            display: grid;
            gap: 42px;
            width: 100%;
            max-width: 860px;
            padding: 72px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.94);
            box-shadow: 0 2px 18px rgba(0, 0, 0, 0.12);
            backdrop-filter: blur(4px);
        }}
        .cover-kicker {{
            margin: 0;
            color: #0f766e;
            font-size: 26px;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}
        h1 {{
            margin: 0;
            padding-bottom: 28px;
            border-bottom: 6px solid #3498db;
            color: #2c3e50;
            font-size: 86px;
            font-weight: 900;
            line-height: 1.34;
            letter-spacing: 0;
        }}
        rt {{
            font-size: 0.34em;
            font-weight: 700;
        }}
        .cover-divider {{
            display: none;
        }}
        .cover-translation {{
            margin: 0;
            color: #475569;
            font-size: var(--cover-translation-size, 46px);
            font-weight: 700;
            line-height: 1.38;
            letter-spacing: 0;
        }}
        h1 {{
            font-size: var(--cover-title-size, 86px);
        }}
    </style>
</head>
<body>
    <div class="emoji-texture" aria-hidden="true">
{emoji_texture_html}
    </div>
    <main class="cover-card">
{kicker_html}
        <h1>{article["headlineHtml"]}</h1>
        <div class="cover-divider" aria-hidden="true"></div>
{translation_html}
    </main>
<script>
function fitCoverText() {{
    const card = document.querySelector('.cover-card');
    const title = document.querySelector('h1');
    const translation = document.querySelector('.cover-translation');
    if (!card || !title) {{
        return;
    }}
    let titleSize = 86;
    let translationSize = 48;
    const applySizes = () => {{
        document.body.style.setProperty('--cover-title-size', `${{titleSize}}px`);
        document.body.style.setProperty('--cover-translation-size', `${{translationSize}}px`);
    }};
    applySizes();
    while ((card.scrollHeight > card.clientHeight || title.scrollWidth > title.clientWidth || (translation && translation.scrollWidth > translation.clientWidth)) && titleSize > 48) {{
        titleSize -= 2;
        translationSize = Math.max(30, translationSize - 1);
        applySizes();
    }}
}}
window.addEventListener('load', fitCoverText);
</script>
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


def video_cover_filename(video_filename: str) -> str:
    return f"{Path(video_filename).stem}-cover.png"


def render_segment_video(
    image_path: Path,
    audio_path: Path,
    duration: float,
    output_path: Path,
    options: RenderOptions,
) -> None:
    target_duration = duration + TRAILING_SILENCE_SECONDS
    rounded_duration = max(MIN_SEGMENT_SECONDS, math.ceil(target_duration * options.frame_rate) / options.frame_rate)
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
            "-af",
            f"apad=pad_dur={TRAILING_SILENCE_SECONDS:.3f},{EXPORT_AUDIO_FILTER}",
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


def render_still_video(image_path: Path, duration: float, output_path: Path, options: RenderOptions) -> None:
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
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def render_still_video_with_audio(
    image_path: Path,
    audio_path: Path,
    duration: float,
    output_path: Path,
    options: RenderOptions,
) -> None:
    target_duration = duration + TRAILING_SILENCE_SECONDS
    rounded_duration = max(MIN_SEGMENT_SECONDS, math.ceil(target_duration * options.frame_rate) / options.frame_rate)
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
            "-af",
            f"apad=pad_dur={TRAILING_SILENCE_SECONDS:.3f},{EXPORT_AUDIO_FILTER}",
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
            "-movflags",
            "+faststart",
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
    cover_path: Path | None = None,
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
            video_path = temp_path / f"{index:03d}-{segment.key}.mp4"

            html_path.write_text(render_html(article, segment, options), encoding="utf-8")
            audio_path = cached_sentence_audio_path(segment.text, options.speaker)
            render_screenshot(chromium, html_path, image_path, options)
            if index == 1 and cover_path:
                cover_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(image_path, cover_path)
            render_segment_video(image_path, audio_path, wav_duration(audio_path), video_path, options)
            segment_paths.append(video_path)

        concatenate_segments(segment_paths, temp_path / "segments.txt", output_path)


def render_article_cover(article: dict, output_path: Path, options: RenderOptions) -> None:
    chromium = chromium_command()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="learn-japanese-cover-") as temp_dir:
        html_path = Path(temp_dir) / "cover.html"
        html_path.write_text(render_article_cover_html(article, options), encoding="utf-8")
        render_screenshot(chromium, html_path, output_path, options)


def render_quiz_video(quiz: dict, output_path: Path, options: RenderOptions, cover_path: Path | None = None) -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required for CLI video rendering.")

    wait_for_voicevox(DEFAULT_VOICEVOX_TIMEOUT)
    chromium = chromium_command()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="learn-japanese-quiz-render-") as temp_dir:
        temp_path = Path(temp_dir)
        html_path = temp_path / "quiz.html"
        image_path = temp_path / "quiz.png"
        story_text = "\n".join(str(line.get("jp", "")) for line in quiz.get("passage", []) if line.get("jp"))
        html_path.write_text(render_quiz_html(quiz, options), encoding="utf-8")
        audio_path = cached_sentence_audio_path(story_text, options.speaker)
        render_screenshot(chromium, html_path, image_path, options)
        if cover_path:
            cover_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(image_path, cover_path)
        render_still_video_with_audio(
            image_path,
            audio_path,
            wav_duration(audio_path),
            output_path,
            options,
        )


def render_quiz_cover(quiz: dict, output_path: Path, options: RenderOptions) -> None:
    chromium = chromium_command()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="learn-japanese-quiz-cover-") as temp_dir:
        html_path = Path(temp_dir) / "quiz-cover.html"
        html_path.write_text(render_quiz_html(quiz, options), encoding="utf-8")
        render_screenshot(chromium, html_path, output_path, options)


def quiz_video_filename(quiz_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", quiz_id).strip("-") or "story-quiz"
    return f"story-quiz-{slug}.mp4"


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
