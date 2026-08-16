#!/usr/bin/env python3

from __future__ import annotations

import argparse
import math
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

from scripts import article_store
from scripts.generate_site import primary_articles
from scripts.render_video import html_base_text, split_html_sentences
from scripts.voicevox_cache import (
    DEFAULT_VOICEVOX_BASE_URL,
    DEFAULT_VOICEVOX_PROSODY,
    VoicevoxRequestError,
    cached_voicevox_wav,
    normalize_voicevox_prosody,
)


DIST_DIR = ROOT / "dist"
DEFAULT_OUTPUT_PATH = DIST_DIR / "japanese-study-record-all-articles-audio.epub"
DEFAULT_TITLE = "日本語の勉強記録 · 全記事集"
DEFAULT_AUTHOR = "ドキドキ団子"
DEFAULT_LANGUAGE = "ja"
DEFAULT_SPEAKER = 9
DEFAULT_AUDIO_FORMAT = "mp3"
DEFAULT_TRAILING_SILENCE = 0.18
FIXED_LAYOUT_WIDTH = 1200
FIXED_LAYOUT_HEIGHT = 1800
EPUB_LAYOUT_CSS_PATH = ROOT / "assets" / "epub-layout.css"
EPUB_COVER_IMAGE_PATH = ROOT / "assets" / "epub-cover-all-articles.png"
EPUB_COVER_IMAGE_HREF = "images/epub-cover-all-articles.png"
EPUB_COVER_IMAGE_MEDIA_TYPE = "image/png"


@dataclass(frozen=True)
class AudioSettings:
    speaker: int
    base_url: str
    prosody: dict
    trailing_silence: float
    audio_format: str


@dataclass(frozen=True)
class SectionAudio:
    id: str
    href: str
    bytes_: bytes
    media_type: str
    duration_seconds: float


@dataclass(frozen=True)
class SectionPage:
    page_id: str
    href: str
    title: str
    body: str
    audio: SectionAudio


@dataclass(frozen=True)
class Chapter:
    index: int
    article: dict
    chapter_audio: SectionAudio
    opener_href: str
    opener_body_html: str
    section_pages: tuple[SectionPage, ...]


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
    return EPUB_LAYOUT_CSS_PATH.read_text(encoding="utf-8")

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
ol,
p,
section,
ul {
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
  padding: 84px 96px 88px;
}

.page__inner {
  position: relative;
  z-index: 1;
  width: 1008px;
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
  gap: 20px;
}

.article-header,
.article-header--balanced,
.article-header--compact {
  width: 100%;
  max-width: 100%;
  margin: 0 0 8px;
}

.article-meta,
.kicker {
  margin: 0 0 14px;
  color: #94603a;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.article-title,
h1 {
  margin: 0;
  color: #1d252d;
  font-family: "Noto Serif JP", "Source Han Serif", "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 52px;
  font-weight: 600;
  line-height: 1.18;
  letter-spacing: -0.01em;
}

.article-title--balanced {
  font-size: 49px;
  line-height: 1.15;
}

.article-title--compact {
  font-size: 46px;
  line-height: 1.13;
  letter-spacing: -0.015em;
}

.title-rule {
  width: 212px;
  height: 4px;
  margin: 18px 0 0;
  border-radius: 999px;
  background: linear-gradient(90deg, #2f6f69 0%, rgba(47, 111, 105, 0.18) 100%);
}

.story-body {
  -webkit-box-flex: 1;
  -webkit-flex: 1 1 auto;
  flex: 1 1 auto;
  min-height: 0;
}

.story-body--overview {
  display: -webkit-box;
  display: -webkit-flex;
  display: flex;
  -webkit-box-orient: vertical;
  -webkit-box-direction: normal;
  -webkit-flex-direction: column;
  flex-direction: column;
  -webkit-box-pack: start;
  -webkit-justify-content: flex-start;
  justify-content: flex-start;
  gap: 18px;
  padding-bottom: 10px;
}

.story-body--section {
  display: -webkit-box;
  display: -webkit-flex;
  display: flex;
  -webkit-box-orient: vertical;
  -webkit-box-direction: normal;
  -webkit-flex-direction: column;
  flex-direction: column;
  gap: 22px;
}

.jp-only-group,
.section-card {
  margin: 0;
  padding: 0;
}

.jp-copy,
.paragraph-japanese {
  margin: 0;
  color: #1f2832;
  font-family: "Noto Serif JP", "Source Han Serif", "Hiragino Mincho ProN", "Yu Mincho", serif;
  font-size: 31px;
  font-weight: 500;
  line-height: 1.58;
}

.section-card .jp-copy,
.section-card .paragraph-japanese {
  font-size: 35px;
  line-height: 1.62;
}

.section-shell {
  display: -webkit-box;
  display: -webkit-flex;
  display: flex;
  -webkit-box-orient: vertical;
  -webkit-box-direction: normal;
  -webkit-flex-direction: column;
  flex-direction: column;
  gap: 22px;
  min-height: 0;
}

.section-label {
  margin: 0;
  color: #2f6f69;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.note-card {
  min-height: 0;
  padding: 22px 24px 24px;
  border: 1px solid rgba(101, 113, 123, 0.26);
  border-radius: 28px;
  background: rgba(255, 252, 247, 0.82);
}

.notes-column {
  display: -webkit-box;
  display: -webkit-flex;
  display: flex;
  -webkit-box-orient: vertical;
  -webkit-box-direction: normal;
  -webkit-flex-direction: column;
  flex-direction: column;
  gap: 18px;
}

.note-title,
h2 {
  margin: 0 0 12px;
  color: #234d4a;
  font-size: 27px;
  font-weight: 700;
  line-height: 1.2;
}

.phrase-note {
  margin: 0;
  color: #425362;
  font-size: 25px;
  font-weight: 500;
  line-height: 1.5;
}

.audio-card {
  display: block;
}

.audio-label {
  display: block;
  margin: 0 0 10px;
  color: #234d4a;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}

.audio-label span {
  display: block;
  margin-top: 4px;
  color: #556473;
  font-size: 18px;
  font-weight: 500;
}

.audio-player {
  display: block;
  width: 100%;
  min-height: 62px;
}

.audio-player:focus {
  outline: 2px solid #2f6f69;
  outline-offset: 4px;
}

.vocabulary-list {
  margin: 0;
  padding-left: 28px;
  color: #1f2832;
  font-size: 24px;
  line-height: 1.45;
}

.vocabulary-list li {
  margin-bottom: 10px;
}

.vocabulary-list--section {
  font-size: 23px;
}

.section-footer,
.page-footer {
  margin-top: auto;
  padding-top: 4px;
  color: #61707d;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.2;
  text-transform: uppercase;
}

.title-translation,
.vocabulary-note {
  margin: 0;
  color: #465665;
  font-size: 24px;
  font-weight: 500;
  line-height: 1.5;
}

.toc {
  margin: 8px 0 0;
  padding-left: 34px;
  color: #1f2832;
  font-size: 28px;
  line-height: 1.44;
}

.toc li {
  margin: 0 0 16px;
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
        </div>
      </div>
    </nav>"""
    return root_xhtml_document(title, body)


def intro_page(title: str, chapters: tuple[Chapter, ...]) -> str:
    body = f"""    <div class="page-wrap">
      <section class="page">
        <div class="page__inner">
        <h1>{xml_escape(title)}</h1>
        <p class="title-translation">{len(chapters)} Japanese reading articles to read, listen to, and study one section at a time.</p>
        <p class="vocabulary-note">Use your EPUB reader’s table of contents to choose a chapter.</p>
        </div>
      </section>
    </div>"""
    return xhtml_document(title, body)


def cover_page(title: str, author: str) -> str:
    body = f"""    <div class="cover-page" role="doc-cover">
      <img class="cover-page__image" src="../{EPUB_COVER_IMAGE_HREF}" alt="{xml_escape(title)} — {xml_escape(author)}"/>
    </div>"""
    return xhtml_document(title, body)


def chapter_overview_xhtml(chapter: Chapter) -> str:
    article = chapter.article
    header_class, title_class = article_title_layout(article)
    body = f"""    <div class="page-wrap">
      <article class="page">
        <div class="page__inner">
        <header class="{header_class}">
          <p class="article-meta">Chapter {chapter.index} · {xml_escape(article["date"])} · {xml_escape(article.get("level", ""))}</p>
          <h1 class="{title_class}">{article["headlineHtml"]}</h1>
          <div class="title-rule"></div>
          <section class="note-card" aria-label="Audio">
            <div class="audio-card">
              <span class="audio-label">▶ Article audio <span>Play the full article</span></span>
              <audio class="audio-player" controls="controls" preload="none" src="../{xml_escape(chapter.chapter_audio.href)}">
                <p>This article includes embedded audio.</p>
              </audio>
            </div>
          </section>
        </header>
        <main class="story-body story-body--overview">
{chapter.opener_body_html}
        </main>
        </div>
      </article>
    </div>"""
    return xhtml_document(article["title"], body)


def section_page_xhtml(article: dict, chapter_index: int, section_index: int, section_count: int, paragraph: dict, audio: SectionAudio, vocabulary_items: tuple[dict, ...]) -> str:
    phrase_note = str(paragraph.get("translation", "")).strip()
    vocabulary_html = render_vocabulary_items(vocabulary_items)
    notes_body = (
        f'          <p class="phrase-note" lang="en" xml:lang="en">{xml_escape(phrase_note)}</p>'
        if phrase_note
        else '          <p class="phrase-note">No phrase note for this section.</p>'
    )
    body = f"""    <div class="page-wrap">
      <article class="page">
        <div class="page__inner">
        <p class="article-meta">Chapter {chapter_index} · Section {section_index} of {section_count}</p>
        <main class="story-body story-body--section">
          <div class="section-shell">
            <p class="section-label">{xml_escape(article["title"])}</p>
            <section class="section-card">
              <p class="jp-copy paragraph-japanese">{paragraph["html"]}</p>
            </section>
            <div class="notes-column">
              <section class="note-card">
                <h2>Phrase note</h2>
{notes_body}
              </section>
              <section class="note-card">
                <h2>Vocabulary</h2>
                <ul class="vocabulary-list vocabulary-list--section">
{vocabulary_html}
                </ul>
              </section>
              <section class="note-card" aria-label="Audio">
                <div class="audio-card">
                  <span class="audio-label">▶ Section audio <span>Play this section only</span></span>
                  <audio class="audio-player" controls="controls" preload="none" src="../{xml_escape(audio.href)}">
                    <p>This section includes embedded audio.</p>
                  </audio>
                </div>
              </section>
            </div>
          </div>
          <p class="section-footer">Section {section_index} study page</p>
        </main>
        </div>
      </article>
    </div>"""
    return xhtml_document(article["title"], body)


def render_vocabulary_items(items: tuple[dict, ...]) -> str:
    if not items:
        return '                  <li>No vocabulary note on this page.</li>'
    return "\n".join(
        f'                  <li><strong>{xml_escape(item["term"])}</strong>: {xml_escape(item["meaning"])}</li>'
        for item in items
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


def package_document(book_uuid: str, title: str, author: str, chapters: tuple[Chapter, ...], spine_pages: tuple[SpinePage, ...]) -> str:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest_items = [
        '    <item id="nav" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '    <item id="style" href="styles/book.css" media-type="text/css"/>',
        f'    <item id="cover-image" href="{EPUB_COVER_IMAGE_HREF}" media-type="{EPUB_COVER_IMAGE_MEDIA_TYPE}" properties="cover-image"/>',
    ]
    for page in spine_pages:
        manifest_items.append(f'    <item id="{page.id}" href="{page.href}" media-type="application/xhtml+xml"/>')
    total_duration = 0.0
    for chapter in chapters:
        manifest_items.append(
            f'    <item id="{chapter.chapter_audio.id}" href="{chapter.chapter_audio.href}" media-type="{chapter.chapter_audio.media_type}"/>'
        )
        total_duration += chapter.chapter_audio.duration_seconds
        for section_page in chapter.section_pages:
            audio = section_page.audio
            manifest_items.append(
                f'    <item id="{audio.id}" href="{audio.href}" media-type="{audio.media_type}"/>'
            )
            total_duration += audio.duration_seconds
    spine_items = [f'    <itemref idref="{page.id}"/>' for page in spine_pages]
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0" xml:lang="{DEFAULT_LANGUAGE}" prefix="media: http://www.idpf.org/epub/vocab/overlays/# rendition: http://www.idpf.org/vocab/rendition/#">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">urn:uuid:{book_uuid}</dc:identifier>
    <dc:title>{xml_escape(title)}</dc:title>
    <dc:language>{DEFAULT_LANGUAGE}</dc:language>
    <dc:creator>{xml_escape(author)}</dc:creator>
    <meta name="cover" content="cover-image"/>
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
        raise ValueError("No audio clips provided for EPUB audio.")
    if which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required for EPUB audio export.")

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


def select_articles(
    article_ids: tuple[str, ...], runtime_content_dir: Path | None = None
) -> tuple[dict, ...]:
    articles = {
        article["id"]: article
        for article in primary_articles(article_store.load_articles(runtime_content_dir))
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
    segments = [html_base_text(article["headlineHtml"]).strip()]
    for paragraph in article.get("paragraphs", []):
        segments.extend(paragraph_audio_segments(paragraph))
    return tuple(segment for segment in segments if segment)


def paragraph_audio_segments(paragraph: dict) -> tuple[str, ...]:
    return tuple(
        text
        for sentence_html in split_html_sentences(paragraph["html"])
        for text in (html_base_text(sentence_html).strip(),)
        if text
    )


def validate_article_sections(article: dict) -> tuple[dict, ...]:
    paragraphs = tuple(article.get("paragraphs", []))
    if not paragraphs:
        raise ValueError(f'Article {article["id"]} must have at least one paragraph for EPUB export.')
    return paragraphs


def chunk_vocabulary(vocabulary: tuple[dict, ...], chunk_count: int) -> tuple[tuple[dict, ...], ...]:
    if chunk_count <= 0:
        return tuple()
    if not vocabulary:
        return tuple(() for _ in range(chunk_count))
    size = max(1, math.ceil(len(vocabulary) / chunk_count))
    chunks = []
    for index in range(chunk_count):
        start = index * size
        end = start + size
        chunks.append(vocabulary[start:end])
    while len(chunks) < chunk_count:
        chunks.append(())
    return tuple(tuple(chunk) for chunk in chunks[:chunk_count])


def build_overview_body(paragraphs: tuple[dict, ...]) -> str:
    return "\n".join(
        f"""          <section class="jp-only-group paragraph">
          <p class="jp-copy paragraph-japanese">{paragraph["html"]}</p>
        </section>"""
        for paragraph in paragraphs
    )


def build_section_audio(chapter_index: int, section_index: int, paragraph: dict, settings: AudioSettings) -> SectionAudio:
    wav_paths = [fetch_audio_wav_path(text, settings) for text in paragraph_audio_segments(paragraph)]
    audio_bytes, duration_seconds = combine_audio(wav_paths, settings.audio_format)
    return SectionAudio(
        id=f"chapter-{chapter_index}-section-{section_index}-audio",
        href=f"audio/article-{chapter_index}-section-{section_index}.{settings.audio_format}",
        bytes_=audio_bytes,
        media_type=audio_media_type(settings.audio_format),
        duration_seconds=duration_seconds,
    )


def build_chapter_audio(chapter_index: int, article: dict, settings: AudioSettings) -> SectionAudio:
    wav_paths = [fetch_audio_wav_path(text, settings) for text in article_audio_segments(article)]
    audio_bytes, duration_seconds = combine_audio(wav_paths, settings.audio_format)
    return SectionAudio(
        id=f"chapter-{chapter_index}-full-audio",
        href=f"audio/article-{chapter_index}-full.{settings.audio_format}",
        bytes_=audio_bytes,
        media_type=audio_media_type(settings.audio_format),
        duration_seconds=duration_seconds,
    )


def build_chapter(article: dict, chapter_index: int, settings: AudioSettings) -> Chapter:
    paragraphs = validate_article_sections(article)
    vocabulary_chunks = chunk_vocabulary(tuple(article.get("vocabulary", [])), len(paragraphs))
    chapter_audio = build_chapter_audio(chapter_index, article, settings)
    section_pages = []
    for section_index, (paragraph, vocabulary_items) in enumerate(zip(paragraphs, vocabulary_chunks, strict=True), start=1):
        audio = build_section_audio(chapter_index, section_index, paragraph, settings)
        href = f"text/article-{chapter_index}-section-{section_index}.xhtml"
        section_pages.append(
            SectionPage(
                page_id=f"chapter-{chapter_index}-section-{section_index}",
                href=href,
                title=f'{article["title"]} Section {section_index}',
                body=section_page_xhtml(
                    article,
                    chapter_index,
                    section_index,
                    len(paragraphs),
                    paragraph,
                    audio,
                    vocabulary_items,
                ),
                audio=audio,
            )
        )

    return Chapter(
        index=chapter_index,
        article=article,
        chapter_audio=chapter_audio,
        opener_href=f"text/article-{chapter_index}-1.xhtml",
        opener_body_html=build_overview_body(paragraphs),
        section_pages=tuple(section_pages),
    )


def build_epub(
    output_path: Path,
    title: str,
    author: str,
    article_ids: tuple[str, ...],
    settings: AudioSettings,
    runtime_content_dir: Path | None = None,
) -> Path:
    if not EPUB_COVER_IMAGE_PATH.is_file():
        raise FileNotFoundError(f"EPUB cover image is missing: {EPUB_COVER_IMAGE_PATH}")
    selected_articles = select_articles(article_ids, runtime_content_dir)
    chapters = tuple(
        build_chapter(article, chapter_index, settings)
        for chapter_index, article in enumerate(selected_articles, start=1)
    )
    spine_pages = [
        SpinePage(
            id="cover",
            href="text/cover.xhtml",
            title=title,
            body=cover_page(title, author),
        ),
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
                id=f"chapter-{chapter.index}-overview",
                href=chapter.opener_href,
                title=chapter.article["title"],
                body=chapter_overview_xhtml(chapter),
            )
        )
        for section_page in chapter.section_pages:
            spine_pages.append(
                SpinePage(
                    id=section_page.page_id,
                    href=section_page.href,
                    title=section_page.title,
                    body=section_page.body,
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
        archive.writestr("OEBPS/content.opf", package_document(book_uuid, title, author, chapters, tuple(spine_pages)))
        archive.write(EPUB_COVER_IMAGE_PATH, f"OEBPS/{EPUB_COVER_IMAGE_HREF}")
        for page in spine_pages:
            archive.writestr(f"OEBPS/{page.href}", page.body)
        for chapter in chapters:
            archive.writestr(f"OEBPS/{chapter.chapter_audio.href}", chapter.chapter_audio.bytes_)
            for section_page in chapter.section_pages:
                archive.writestr(f"OEBPS/{section_page.audio.href}", section_page.audio.bytes_)

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an EPUB 3 with embedded section audio from selected Learn Japanese articles.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to the EPUB file to create.")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Book title to embed in the EPUB metadata.")
    parser.add_argument("--author", default=DEFAULT_AUTHOR, help="Author name to embed in the EPUB metadata and cover.")
    parser.add_argument("--article-id", action="append", dest="article_ids", help="Article id to include. Repeat to export only a selected subset; the default is every primary article.")
    parser.add_argument("--runtime-content-dir", help="Runtime article directory to merge with repo articles. Defaults to CONTENT_DIR or the local runtime-store path.")
    parser.add_argument("--speaker", type=int, default=DEFAULT_SPEAKER, help="VOICEVOX speaker id.")
    parser.add_argument("--voicevox-base-url", default=DEFAULT_VOICEVOX_BASE_URL, help="VOICEVOX base URL.")
    parser.add_argument("--speed-scale", type=float, default=DEFAULT_VOICEVOX_PROSODY["speedScale"])
    parser.add_argument("--pitch-scale", type=float, default=DEFAULT_VOICEVOX_PROSODY["pitchScale"])
    parser.add_argument("--intonation-scale", type=float, default=DEFAULT_VOICEVOX_PROSODY["intonationScale"])
    parser.add_argument("--trailing-silence", type=float, default=DEFAULT_TRAILING_SILENCE, help="Extra silence to append to each sentence clip before section concatenation.")
    parser.add_argument("--audio-format", choices=("mp3", "wav"), default=DEFAULT_AUDIO_FORMAT, help="Pack section audio as mp3 or wav.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runtime_content_dir = Path(args.runtime_content_dir).resolve() if args.runtime_content_dir else None
    available_articles = primary_articles(article_store.load_articles(runtime_content_dir))
    article_ids = tuple(args.article_ids) if args.article_ids else tuple(
        article["id"] for article in available_articles
    )
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
    path = build_epub(
        output_path,
        args.title,
        args.author,
        article_ids,
        settings,
        runtime_content_dir,
    )
    print(path)


if __name__ == "__main__":
    main()
