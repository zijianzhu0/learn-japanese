#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import wave
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from uuid import uuid4
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_site import load_articles, primary_articles
from scripts.render_video import html_base_text, split_html_sentences
from scripts.voicevox_cache import (
    DEFAULT_VOICEVOX_BASE_URL,
    DEFAULT_VOICEVOX_PROSODY,
    VoicevoxRequestError,
    cached_voicevox_wav,
    normalize_voicevox_prosody,
)


DIST_DIR = ROOT / "dist"
DEFAULT_OUTPUT_PATH = DIST_DIR / "tokyo-starter-pack-audio.epub"
DEFAULT_TITLE = "Tokyo Starter Pack"
DEFAULT_LANGUAGE = "ja"
DEFAULT_ARTICLE_IDS = (
    "2026-07-02-imperial-palace-running",
    "2026-07-04-keikyu-direction-from-haneda",
    "2026-07-08-yellow-exit-signs",
)
DEFAULT_SPEAKER = 9
DEFAULT_AUDIO_FORMAT = "mp3"
DEFAULT_TRAILING_SILENCE = 0.18
FIXED_LAYOUT_WIDTH = 1200
FIXED_LAYOUT_HEIGHT = 1800
@dataclass(frozen=True)
class AudioSettings:
    speaker: int
    base_url: str
    prosody: dict
    trailing_silence: float
    audio_format: str


@dataclass(frozen=True)
class Chapter:
    index: int
    article: dict
    chapter_audio_href: str
    chapter_audio_bytes: bytes
    chapter_audio_media_type: str
    chapter_audio_duration_seconds: float
    opener_href: str
    opener_body_html: str
    vocabulary_body_html: str


@dataclass(frozen=True)
class SpinePage:
    id: str
    href: str
    title: str
    body: str


def xhtml_document(title: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{DEFAULT_LANGUAGE}" xml:lang="{DEFAULT_LANGUAGE}">
  <head>
    <title>{xml_escape(title)}</title>
    <meta name="viewport" content="width={FIXED_LAYOUT_WIDTH},height={FIXED_LAYOUT_HEIGHT}"/>
    <link rel="stylesheet" type="text/css" href="../styles/book.css"/>
  </head>
  <body>
{body}
  </body>
</html>
"""


def root_xhtml_document(title: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{DEFAULT_LANGUAGE}" xml:lang="{DEFAULT_LANGUAGE}">
  <head>
    <title>{xml_escape(title)}</title>
    <meta name="viewport" content="width={FIXED_LAYOUT_WIDTH},height={FIXED_LAYOUT_HEIGHT}"/>
    <link rel="stylesheet" type="text/css" href="styles/book.css"/>
  </head>
  <body>
{body}
  </body>
</html>
"""


def book_stylesheet() -> str:
    return """@namespace epub "http://www.idpf.org/2007/ops";

*,
*::before,
*::after {
  box-sizing: border-box;
}

html,
body {
  width: 100%;
  height: 100%;
  margin: 0;
}

body {
  overflow: hidden;
  color: #1f2832;
  font-family: "Noto Sans", "Source Sans 3", "Helvetica Neue", Arial, sans-serif;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.74), transparent 30%),
    radial-gradient(circle at top right, rgba(202, 225, 218, 0.46), transparent 28%),
    linear-gradient(180deg, #f7f2e9 0%, #f1eadf 58%, #ece4d8 100%);
}

article,
audio,
div,
header,
main,
nav,
section {
  display: block;
}

a {
  color: inherit;
  text-decoration: none;
}

.page-wrap {
  position: relative;
  width: 100%;
  height: 100%;
}

.page-wrap::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(92, 79, 64, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(92, 79, 64, 0.026) 1px, transparent 1px);
  background-size: 30px 30px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.66), transparent 88%);
  pointer-events: none;
}

.page {
  position: relative;
  width: 100%;
  height: 100%;
  padding: 86px 100px 88px;
}

.page__inner {
  position: relative;
  z-index: 1;
  width: 1000px;
  max-width: 100%;
  height: 100%;
  margin: 0 auto;
  display: -webkit-box;
  display: -webkit-flex;
  display: flex;
  -webkit-box-orient: vertical;
  -webkit-box-direction: normal;
  -webkit-flex-direction: column;
  flex-direction: column;
}

.article-header {
  width: 860px;
  max-width: 86%;
  margin: 0 0 26px;
}

.article-header--balanced {
  width: 828px;
  margin-bottom: 22px;
}

.article-header--compact {
  width: 796px;
  margin-bottom: 18px;
}

.article-meta,
.kicker {
  margin: 0 0 14px;
  color: #94603a;
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.article-title,
h1 {
  margin: 0;
  color: #1d252d;
  font-family: "Noto Serif JP", "Source Han Serif", "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 56px;
  font-weight: 600;
  line-height: 1.22;
  letter-spacing: -0.01em;
}

.article-title--balanced {
  font-size: 54px;
  line-height: 1.18;
}

.article-title--compact {
  font-size: 52px;
  line-height: 1.15;
  letter-spacing: -0.015em;
}

.title-rule {
  width: 196px;
  height: 4px;
  margin: 20px 0 18px;
  border-radius: 999px;
  background: linear-gradient(90deg, #2f6f69 0%, rgba(47, 111, 105, 0.18) 100%);
}

.article-header--balanced .title-rule {
  margin: 16px 0 14px;
}

.article-header--compact .title-rule {
  width: 178px;
  margin: 14px 0 12px;
}

.title-translation,
.article-subtitle {
  margin: 0;
  color: #465665;
  font-size: 22px;
  font-weight: 500;
  line-height: 1.42;
}

.audio-panel {
  margin: 20px 0 0;
}

.article-header--balanced .audio-panel {
  margin-top: 16px;
}

.article-header--compact .audio-panel {
  margin-top: 14px;
}

.audio-card {
  display: inline-block;
  padding: 12px 18px 12px 16px;
  border: 1px solid rgba(101, 113, 123, 0.34);
  border-radius: 22px;
  background: rgba(255, 252, 247, 0.82);
}

.audio-label {
  display: block;
  margin: 0 0 8px;
  color: #234d4a;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.15;
}

.audio-label span {
  color: #556473;
  font-size: 17px;
  font-weight: 500;
}

.audio-player {
  display: block;
  width: 338px;
  min-width: 338px;
  min-height: 56px;
}

.audio-player:focus {
  outline: 2px solid #2f6f69;
  outline-offset: 4px;
}

.story-body {
  -webkit-box-flex: 1;
  -webkit-flex: 1 1 auto;
  flex: 1 1 auto;
  min-height: 0;
  display: -webkit-box;
  display: -webkit-flex;
  display: flex;
  -webkit-box-orient: vertical;
  -webkit-box-direction: normal;
  -webkit-flex-direction: column;
  flex-direction: column;
  -webkit-box-pack: justify;
  -webkit-justify-content: space-between;
  justify-content: space-between;
  gap: 22px;
  padding-bottom: 12px;
}

.bilingual-group {
  margin: 0;
  padding: 0;
}

.jp-copy,
.paragraph-japanese {
  margin: 0;
  color: #1f2832;
  font-family: "Noto Serif JP", "Source Han Serif", "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 33px;
  font-weight: 500;
  line-height: 1.64;
}

.en-copy,
.translation {
  margin: 10px 0 0;
  color: #4d5d6d;
  font-family: "Noto Sans", "Source Sans 3", "Helvetica Neue", Arial, sans-serif;
  font-size: 21px;
  font-weight: 500;
  line-height: 1.46;
}

.vocabulary-note {
  margin: 0 0 12px;
  color: #4d5d6d;
  font-size: 21px;
  font-weight: 500;
  line-height: 1.42;
}

.toc {
  margin: 18px 0 0;
  padding-left: 34px;
  color: #1f2832;
  font-size: 26px;
  line-height: 1.42;
}

.toc li {
  margin: 0 0 16px;
}

.vocabulary-list {
  margin: 0;
  padding-left: 34px;
  color: #1f2832;
  font-size: 24px;
  line-height: 1.42;
}

.vocabulary-list li {
  margin-bottom: 12px;
}

.back-link,
.page-footer {
  margin-top: auto;
  padding-top: 14px;
  color: #61707d;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.2;
  text-transform: uppercase;
}

ruby {
  ruby-position: over;
  ruby-align: center;
}

rt {
  color: #2f6f69;
  font-size: 0.44em;
  font-weight: 400;
  line-height: 1;
}

rp {
  display: none;
}
"""


def article_title_layout(article: dict) -> tuple[str, str]:
    title_text = "".join(html_base_text(article.get("headlineHtml", "")).split())
    subtitle_text = " ".join(str(article.get("titleTranslation", "")).split())
    body_score = sum(len("".join(html_base_text(paragraph.get("html", "")).split())) for paragraph in article.get("paragraphs", []))
    translation_score = sum(len(" ".join(str(paragraph.get("translation", "")).split())) for paragraph in article.get("paragraphs", []))

    layout_score = len(title_text) * 1.9 + len(subtitle_text) * 0.55
    if body_score > 320:
        layout_score += 8
    if translation_score > 480:
        layout_score += 6

    if layout_score >= 105:
        return ("article-header article-header--compact", "article-title article-title--compact")
    if layout_score >= 80:
        return ("article-header article-header--balanced", "article-title article-title--balanced")
    return ("article-header", "article-title")


def nav_document(title: str, chapters: tuple[Chapter, ...]) -> str:
    items = "\n".join(
        f'        <li><a href="{xml_escape(chapter.opener_href)}">{xml_escape(chapter.article["title"])}</a></li>'
        for chapter in chapters
    )
    body = f"""    <nav epub:type="toc" id="toc" class="page-wrap">
      <div class="page">
        <div class="page__inner">
        <p class="kicker">Contents</p>
        <h1>{xml_escape(title)}</h1>
        <ol class="toc">
{items}
        </ol>
        <p class="page-footer">Fixed layout · {FIXED_LAYOUT_WIDTH}×{FIXED_LAYOUT_HEIGHT}</p>
        </div>
      </div>
    </nav>"""
    return root_xhtml_document(title, body)


def intro_page(title: str, chapters: tuple[Chapter, ...]) -> str:
    toc_items = "\n".join(
        f'        <li><a href="{xml_escape(chapter.opener_href)}">{xml_escape(chapter.article["title"])}</a></li>'
        for chapter in chapters
    )
    body = f"""    <div class="page-wrap">
      <section class="page">
        <div class="page__inner">
        <p class="kicker">Japanese Reading EPUB</p>
        <h1>{xml_escape(title)}</h1>
        <p class="title-translation">A fixed-layout EPUB styled from the IG-video look, with embedded chapter audio and a single play/pause control on each chapter opener.</p>
        <p class="vocabulary-note">Each article stays on a single 1200×1800 page with native EPUB audio controls, and the vocabulary list sits on its own fixed page.</p>
        <h2>Contents</h2>
        <ol class="toc">
{toc_items}
        </ol>
        <h2>Fallback</h2>
        <p class="vocabulary-note">The article pages use normal text flow with ruby markup and standard audio playback controls so the layout and media remain available without JavaScript.</p>
        <p class="page-footer">Fixed layout · {FIXED_LAYOUT_WIDTH}×{FIXED_LAYOUT_HEIGHT}</p>
        </div>
      </section>
    </div>"""
    return xhtml_document(title, body)


def chapter_opener_xhtml(chapter: Chapter) -> str:
    article = chapter.article
    header_class, title_class = article_title_layout(article)
    body = f"""    <div class="page-wrap">
      <article class="page">
        <div class="page__inner">
        <header class="{header_class}">
          <p class="article-meta">Chapter {chapter.index} · {xml_escape(article["date"])} · {xml_escape(article.get("level", ""))}</p>
          <h1 class="{title_class}">{article["headlineHtml"]}</h1>
          <div class="title-rule"></div>
          <p class="article-subtitle title-translation" lang="en" xml:lang="en">{xml_escape(article.get("titleTranslation", ""))}</p>
          <section class="audio-panel" aria-label="Audio">
            <div class="audio-card">
              <span class="audio-label">▶ 音声を聞く <span>Play audio</span></span>
              <audio class="audio-player" controls="controls" preload="none" src="../{xml_escape(chapter.chapter_audio_href)}">
                <p>This chapter includes embedded audio.</p>
              </audio>
            </div>
          </section>
        </header>
        <main class="story-body">
{chapter.opener_body_html}
        </main>
        </div>
      </article>
    </div>"""
    return xhtml_document(article["title"], body)


def vocabulary_page_xhtml(chapter: Chapter) -> str:
    article = chapter.article
    body = f"""    <div class="page-wrap">
      <article class="page">
        <div class="page__inner">
        <p class="article-meta">Chapter {chapter.index} · Vocabulary</p>
        <h2>{xml_escape(article.get("vocabularyTitle", "Vocabulary"))}</h2>
        <p class="vocabulary-note">Key words from this article.</p>
{chapter.vocabulary_body_html}
        <p class="back-link"><a href="../toc.xhtml">Back to contents</a></p>
        </div>
      </article>
    </div>"""
    return xhtml_document(article["title"], body)


def render_vocabulary(article: dict) -> str:
    return "\n".join(
        f'        <li><strong>{xml_escape(item["term"])}</strong>: {xml_escape(item["meaning"])}</li>'
        for item in article.get("vocabulary", [])
    )


def ncx_document(book_uuid: str, title: str, chapters: tuple[Chapter, ...]) -> str:
    nav_points = "\n".join(
        f"""    <navPoint id="nav-{chapter.index}" playOrder="{chapter.index}">
      <navLabel>
        <text>{xml_escape(chapter.article["title"])}</text>
      </navLabel>
      <content src="{xml_escape(chapter.opener_href)}"/>
    </navPoint>"""
        for chapter in chapters
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{book_uuid}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle>
    <text>{xml_escape(title)}</text>
  </docTitle>
  <navMap>
{nav_points}
  </navMap>
</ncx>
"""


def package_document(book_uuid: str, title: str, chapters: tuple[Chapter, ...], spine_pages: tuple[SpinePage, ...]) -> str:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest_items = [
        '    <item id="nav" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '    <item id="style" href="styles/book.css" media-type="text/css"/>',
    ]
    for page in spine_pages:
        manifest_items.append(
            f'    <item id="{page.id}" href="{page.href}" media-type="application/xhtml+xml"/>'
        )
    for chapter in chapters:
        manifest_items.append(
            f'    <item id="chapter-audio-{chapter.index}" href="{chapter.chapter_audio_href}" media-type="{chapter.chapter_audio_media_type}"/>'
        )
    spine_items = [f'    <itemref idref="{page.id}"/>' for page in spine_pages]
    total_duration = sum(chapter.chapter_audio_duration_seconds for chapter in chapters)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0" xml:lang="{DEFAULT_LANGUAGE}" prefix="media: http://www.idpf.org/epub/vocab/overlays/# rendition: http://www.idpf.org/vocab/rendition/#">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">urn:uuid:{book_uuid}</dc:identifier>
    <dc:title>{xml_escape(title)}</dc:title>
    <dc:language>{DEFAULT_LANGUAGE}</dc:language>
    <dc:creator>OpenAI Codex</dc:creator>
    <meta property="dcterms:modified">{timestamp}</meta>
    <meta property="media:duration">{format_metadata_duration(total_duration)}</meta>
    <meta property="rendition:layout">pre-paginated</meta>
    <meta property="rendition:orientation">portrait</meta>
    <meta property="rendition:spread">none</meta>
  </metadata>
  <manifest>
{chr(10).join(manifest_items)}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine_items)}
  </spine>
</package>
"""


def container_document() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def format_metadata_duration(seconds: float) -> str:
    total_ms = int(round(max(0.0, seconds) * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours}:{minutes:02d}:{secs:02d}.{millis:03d}"


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
    return frames / float(rate)


def audio_media_type(audio_format: str) -> str:
    if audio_format == "mp3":
        return "audio/mpeg"
    if audio_format == "wav":
        return "audio/wav"
    raise ValueError(f"Unsupported audio format: {audio_format}")


def transcode_audio(wav_path: Path, output_format: str) -> bytes:
    if output_format == "wav":
        return wav_path.read_bytes()

    if output_format != "mp3":
        raise ValueError(f"Unsupported audio format: {output_format}")
    if which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required for mp3 EPUB audio export.")

    with tempfile.TemporaryDirectory(prefix="learn-japanese-epub-audio-") as temp_dir:
        output_path = Path(temp_dir) / "audio.mp3"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(wav_path),
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
        return output_path.read_bytes()


def combine_audio(wav_paths: list[Path], output_format: str) -> tuple[bytes, float]:
    if not wav_paths:
        raise ValueError("No audio clips provided for chapter audio.")
    if which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required for chapter audio EPUB export.")

    with tempfile.TemporaryDirectory(prefix="learn-japanese-epub-combine-") as temp_dir:
        temp_path = Path(temp_dir)
        list_path = temp_path / "inputs.txt"
        concat_lines = []
        for wav_path in wav_paths:
            escaped_path = wav_path.as_posix().replace("'", "'\\''")
            concat_lines.append(f"file '{escaped_path}'")
        list_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

        combined_wav = temp_path / "combined.wav"
        subprocess.run(
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
                str(list_path),
                "-c",
                "copy",
                str(combined_wav),
            ],
            check=True,
            capture_output=True,
        )
        return transcode_audio(combined_wav, output_format), wav_duration_seconds(combined_wav)


def select_articles(article_ids: tuple[str, ...]) -> tuple[dict, ...]:
    articles = {
        article["id"]: article
        for article in primary_articles(load_articles())
    }
    selected = []
    for article_id in article_ids:
        article = articles.get(article_id)
        if article is None:
            raise ValueError(f"Article not found: {article_id}")
        selected.append(article)
    return tuple(selected)


def fetch_audio_wav_path(text: str, settings: AudioSettings) -> Path:
    try:
        _wav_audio, _cache_hit, wav_path = cached_voicevox_wav(
            text,
            settings.speaker,
            base_url=settings.base_url,
            prosody=settings.prosody,
            trailing_silence=settings.trailing_silence,
            timeout=60,
        )
    except VoicevoxRequestError as exc:
        raise SystemExit(exc.message) from exc
    return wav_path


def article_audio_segments(article: dict) -> tuple[str, ...]:
    segments = [html_base_text(article["headlineHtml"])]
    for paragraph in article.get("paragraphs", []):
        for sentence_html in split_html_sentences(paragraph["html"]):
            segments.append(html_base_text(sentence_html))
    return tuple(segment for segment in segments if segment)


def build_chapter(article: dict, chapter_index: int, settings: AudioSettings) -> Chapter:
    chapter_wav_paths = [fetch_audio_wav_path(text, settings) for text in article_audio_segments(article)]
    paragraph_sections = []

    for paragraph in article.get("paragraphs", []):
        translation = str(paragraph.get("translation", "")).strip()
        translation_html = f'\n          <p class="en-copy translation" lang="en" xml:lang="en">{xml_escape(translation)}</p>' if translation else ""
        paragraph_sections.append(
            f"""          <section class="bilingual-group paragraph">
          <p class="jp-copy paragraph-japanese">{paragraph["html"]}</p>{translation_html}
        </section>"""
        )

    opener_body_html = "\n".join(paragraph_sections)

    chapter_audio_bytes, chapter_audio_duration = combine_audio(chapter_wav_paths, settings.audio_format)
    return Chapter(
        index=chapter_index,
        article=article,
        chapter_audio_href=f"audio/article-{chapter_index}-full.{settings.audio_format}",
        chapter_audio_bytes=chapter_audio_bytes,
        chapter_audio_media_type=audio_media_type(settings.audio_format),
        chapter_audio_duration_seconds=chapter_audio_duration,
        opener_href=f"text/article-{chapter_index}-1.xhtml",
        opener_body_html=opener_body_html,
        vocabulary_body_html=f"""        <ol class="vocabulary-list">
{render_vocabulary(article)}
        </ol>""",
    )


def build_epub(
    output_path: Path,
    title: str,
    article_ids: tuple[str, ...],
    settings: AudioSettings,
) -> Path:
    selected_articles = select_articles(article_ids)
    chapters = tuple(
        build_chapter(article, chapter_index, settings)
        for chapter_index, article in enumerate(selected_articles, start=1)
    )
    spine_pages = [
        SpinePage(
            id="intro",
            href="text/intro.xhtml",
            title=title,
            body=intro_page(title, chapters),
        )
    ]
    for chapter in chapters:
        spine_pages.append(
            SpinePage(
                id=f"chapter-{chapter.index}-opener",
                href=chapter.opener_href,
                title=chapter.article["title"],
                body=chapter_opener_xhtml(chapter),
            )
        )
        spine_pages.append(
            SpinePage(
                id=f"chapter-{chapter.index}-vocabulary",
                href=f"text/article-{chapter.index}-vocabulary.xhtml",
                title=chapter.article["title"],
                body=vocabulary_page_xhtml(chapter),
            )
        )

    book_uuid = str(uuid4())
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", container_document())
        archive.writestr("OEBPS/styles/book.css", book_stylesheet())
        archive.writestr("OEBPS/toc.xhtml", nav_document(title, chapters))
        archive.writestr("OEBPS/toc.ncx", ncx_document(book_uuid, title, chapters))
        archive.writestr("OEBPS/content.opf", package_document(book_uuid, title, chapters, tuple(spine_pages)))
        for page in spine_pages:
            archive.writestr(f"OEBPS/{page.href}", page.body)
        for chapter in chapters:
            archive.writestr(f"OEBPS/{chapter.chapter_audio_href}", chapter.chapter_audio_bytes)

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fixed-layout EPUB 3 with embedded chapter audio from selected Learn Japanese articles.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to the EPUB file to create.")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Book title to embed in the EPUB metadata.")
    parser.add_argument("--article-id", action="append", dest="article_ids", help="Article id to include. Repeat to override the default three-article set.")
    parser.add_argument("--speaker", type=int, default=DEFAULT_SPEAKER, help="VOICEVOX speaker id.")
    parser.add_argument("--voicevox-base-url", default=DEFAULT_VOICEVOX_BASE_URL, help="VOICEVOX base URL.")
    parser.add_argument("--speed-scale", type=float, default=DEFAULT_VOICEVOX_PROSODY["speedScale"])
    parser.add_argument("--pitch-scale", type=float, default=DEFAULT_VOICEVOX_PROSODY["pitchScale"])
    parser.add_argument("--intonation-scale", type=float, default=DEFAULT_VOICEVOX_PROSODY["intonationScale"])
    parser.add_argument("--trailing-silence", type=float, default=DEFAULT_TRAILING_SILENCE, help="Extra silence to append to each sentence clip before chapter concatenation.")
    parser.add_argument("--audio-format", choices=("mp3", "wav"), default=DEFAULT_AUDIO_FORMAT, help="Pack chapter audio as mp3 or wav.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    article_ids = tuple(args.article_ids) if args.article_ids else DEFAULT_ARTICLE_IDS
    output_path = Path(args.output).resolve()
    settings = AudioSettings(
        speaker=args.speaker,
        base_url=args.voicevox_base_url,
        prosody=normalize_voicevox_prosody(
            {
                "speedScale": args.speed_scale,
                "pitchScale": args.pitch_scale,
                "intonationScale": args.intonation_scale,
            }
        ),
        trailing_silence=args.trailing_silence,
        audio_format=args.audio_format,
    )
    path = build_epub(output_path, args.title, article_ids, settings)
    print(path)


if __name__ == "__main__":
    main()
