#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error as urlerror
from urllib import parse, request as urlrequest

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scripts import article_store, generate_site
from scripts.render_video import (
    DEFAULT_VOICEVOX_TIMEOUT,
    EXPORT_AUDIO_FILTER,
    RenderOptions,
    build_segments,
    find_video_quiz,
    quiz_video_filename,
    render_html,
    render_article_cover,
    render_article_video,
    render_quiz_cover,
    render_quiz_video,
    video_cover_filename,
)
from scripts.voicevox_cache import (
    DEFAULT_VOICEVOX_PROSODY,
    VoicevoxRequestError,
    cache_path,
    cached_voicevox_wav,
    normalize_voicevox_prosody,
    voicevox_request,
)


DEFAULT_HOST = os.environ.get("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT", "8765"))
DEFAULT_PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "127.0.0.1")
VOICEVOX_BASE_URL = os.environ.get("VOICEVOX_BASE_URL", "http://127.0.0.1:50021")
DEFAULT_VOICEVOX_SPEAKER = 9
MAX_TTS_TEXT_CHARS = 500
MAX_VIDEO_UPLOAD_BYTES = 700 * 1024 * 1024
MAX_AGENT_BRIEF_CHARS = 12_000
CODEX_AGENT_TIMEOUT_SECONDS = 300
CODEX_ARTICLE_AGENT_MODEL = "gpt-5.6-terra"
DEEPSEEK_AGENT_MODEL = os.environ.get("DEEPSEEK_AGENT_MODEL", "deepseek-chat")
DEEPSEEK_API_URL = os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
VIDEO_OUTPUT_DIR = PROJECT_DIR / "videos"
FLASHCARD_PROGRESS_PATH = PROJECT_DIR / "data" / "flashcard-progress.json"
FLASHCARD_PROGRESS_LOCK = threading.Lock()
VOICE_SETTINGS_PATH = PROJECT_DIR / "data" / "voice-settings.json"
VOICE_SETTINGS_LOCK = threading.Lock()
RUNTIME_ARTICLE_CONTENT_DIR = article_store.content_dir()


class LearnJapaneseHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = parse.urlsplit(self.path)
        request_path = parsed.path
        if request_path in {"", "/", "/index.html"}:
            self.handle_dynamic_index()
            return

        if request_path == "/data/article-navigation.json":
            self.handle_article_navigation_manifest()
            return

        if request_path == "/data/flashcards.json":
            self.handle_flashcards_manifest()
            return

        if request_path == "/data/ebook-library.json":
            self.handle_ebook_library_manifest()
            return

        dynamic_article = self.find_dynamic_article(request_path)
        if dynamic_article is not None:
            self.handle_dynamic_article(dynamic_article)
            return

        if request_path == "/api/tts/voicevox/status":
            self.handle_voicevox_status()
            return

        if request_path == "/api/voice-settings":
            self.handle_voice_settings_get()
            return

        if request_path == "/api/articles":
            self.handle_articles_get(parsed.query)
            return

        if request_path == "/api/articles/backup":
            self.handle_articles_backup()
            return

        if request_path == "/api/codex/status":
            self.handle_codex_status()
            return

        if request_path == "/api/deepseek/status":
            self.handle_deepseek_status()
            return

        if request_path == "/api/flashcards/progress":
            self.handle_flashcard_progress_get()
            return

        if request_path == "/api/video/preview":
            self.handle_video_preview(parsed.query)
            return

        super().do_GET()

    def do_POST(self) -> None:
        request_path = parse.urlsplit(self.path).path
        if request_path == "/api/articles":
            self.handle_article_create()
            return

        if request_path == "/api/articles/agent":
            self.handle_article_agent_publish()
            return

        if request_path == "/api/tts/voicevox":
            self.handle_voicevox_synthesis()
            return

        if request_path == "/api/tts/voicevox/cache-status":
            self.handle_voicevox_cache_status()
            return

        if request_path == "/api/voice-settings":
            self.handle_voice_settings_update()
            return

        if request_path == "/api/flashcards/progress":
            self.handle_flashcard_progress_update()
            return

        if request_path == "/api/video/convert-mp4":
            self.handle_mp4_conversion()
            return

        if request_path == "/api/video/render":
            self.handle_video_render()
            return

        if request_path == "/api/video/render-url":
            self.handle_video_render_url()
            return

        if request_path == "/api/video/render-cover":
            self.handle_video_cover_render()
            return

        if request_path == "/api/video/render-quiz-url":
            self.handle_quiz_video_render_url()
            return

        if request_path == "/api/video/render-quiz-cover":
            self.handle_quiz_video_cover_render()
            return

        self.send_json(404, {"ok": False, "error": "Unknown API endpoint."})

    def do_DELETE(self) -> None:
        parsed = parse.urlsplit(self.path)
        if parsed.path == "/api/articles":
            self.handle_article_delete(parsed.query)
            return

        self.send_json(404, {"ok": False, "error": "Unknown API endpoint."})

    def runtime_articles(self) -> list[dict]:
        return article_store.load_articles(RUNTIME_ARTICLE_CONTENT_DIR)

    def find_dynamic_article(self, request_path: str) -> dict | None:
        path = request_path.strip("/")
        if not path or not path.endswith(".html") or path in {"flashcards.html", "ig-videos.html"}:
            return None
        try:
            return article_store.find_article(path, RUNTIME_ARTICLE_CONTENT_DIR)
        except ValueError:
            return None

    def send_html(self, status: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def handle_dynamic_index(self) -> None:
        self.send_html(200, generate_site.render_index_html(self.runtime_articles()))

    def handle_dynamic_article(self, article: dict) -> None:
        template = generate_site.ARTICLE_TEMPLATE_PATH.read_text(encoding="utf-8")
        html = generate_site.render_article(
            article,
            template,
            generate_site.file_version(generate_site.ARTICLE_JS_PATH),
        )
        self.send_html(200, html)

    def handle_article_navigation_manifest(self) -> None:
        self.send_json(200, generate_site.article_navigation(self.runtime_articles()))

    def handle_flashcards_manifest(self) -> None:
        self.send_json(200, generate_site.build_flashcards_payload(self.runtime_articles()))

    def handle_ebook_library_manifest(self) -> None:
        self.send_json(200, generate_site.build_ebook_library_payload(self.runtime_articles()))

    def handle_codex_status(self) -> None:
        codex_bin = shutil.which("codex")
        if not codex_bin:
            self.send_json(503, {"ok": False, "error": "Codex CLI is not installed or not on PATH for the server."})
            return
        try:
            result = subprocess.run(
                [codex_bin, "login", "status"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.send_json(503, {"ok": False, "error": "Codex sign-in status timed out."})
            return

        detail = (result.stdout or result.stderr).strip()
        self.send_json(
            200,
            {
                "ok": True,
                "authenticated": result.returncode == 0,
                "status": detail or ("Signed in." if result.returncode == 0 else "Not signed in."),
            },
        )

    def handle_deepseek_status(self) -> None:
        """Report configuration only; never expose the DeepSeek API key."""
        self.send_json(
            200,
            {
                "ok": True,
                "configured": bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()),
                "model": DEEPSEEK_AGENT_MODEL,
            },
        )

    def handle_articles_get(self, query_string: str) -> None:
        params = parse.parse_qs(query_string, keep_blank_values=False)
        article_ref = str(params.get("article_id", [""])[0]).strip()
        if article_ref:
            self.handle_article_detail(article_ref)
            return

        articles = generate_site.primary_articles(self.runtime_articles())
        runtime_count = sum(
            1
            for article in articles
            if article_store.article_storage_path(article, RUNTIME_ARTICLE_CONTENT_DIR).exists()
        )
        self.send_json(
            200,
            {
                "ok": True,
                "content_dir": str(RUNTIME_ARTICLE_CONTENT_DIR),
                "backup_url": "/api/articles/backup",
                "count": len(articles),
                "runtime_count": runtime_count,
                "articles": [
                    {
                        "id": article["id"],
                        "file": article["file"],
                        "title": article["title"],
                        "date": article["date"],
                        "month": article["month"],
                        "navLabel": article["navLabel"],
                        "level": article.get("level", ""),
                        "href": generate_site.article_href(article),
                        "runtime": article_store.article_storage_path(
                            article, RUNTIME_ARTICLE_CONTENT_DIR
                        ).exists(),
                    }
                    for article in articles
                ],
            },
        )

    def handle_article_detail(self, article_ref: str) -> None:
        try:
            article, path = article_store.read_external_article_spec(
                article_ref, RUNTIME_ARTICLE_CONTENT_DIR
            )
        except ValueError as exc:
            self.send_json(404, {"ok": False, "error": str(exc)})
            return

        self.send_json(
            200,
            {
                "ok": True,
                "content_dir": str(RUNTIME_ARTICLE_CONTENT_DIR),
                "article": article,
                "json_path": str(path),
            },
        )

    def parse_article_write_request(self) -> tuple[dict, bool]:
        payload = self.read_json_body()
        if "article" in payload:
            article = payload.get("article")
            overwrite = bool(payload.get("overwrite"))
        else:
            article = dict(payload)
            overwrite = bool(article.pop("overwrite", False))
        if not isinstance(article, dict):
            raise ValueError("Article request must contain an article object.")
        article_store.validate_article_payload(article, enforce_runtime_rules=True)
        return article, overwrite

    def validate_runtime_article_set(self, article_id: str) -> dict:
        articles = self.runtime_articles()
        article = article_store.find_article(article_id, RUNTIME_ARTICLE_CONTENT_DIR)
        generate_site.render_article(
            article,
            generate_site.ARTICLE_TEMPLATE_PATH.read_text(encoding="utf-8"),
            generate_site.file_version(generate_site.ARTICLE_JS_PATH),
        )
        generate_site.render_index_html(articles)
        generate_site.build_flashcards_payload(articles)
        return article

    def handle_article_create(self) -> None:
        try:
            article, overwrite = self.parse_article_write_request()
            saved, target_path = self.save_runtime_article(article, overwrite)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": f"Runtime article publish failed: {exc}"})
            return

        self.send_json(
            201,
            {
                "ok": True,
                "article": {
                    "id": saved["id"],
                    "file": saved["file"],
                    "title": saved["title"],
                    "href": generate_site.article_href(saved),
                    "json_path": str(target_path),
                },
                "content_dir": str(RUNTIME_ARTICLE_CONTENT_DIR),
                "index_url": "/index.html",
                "flashcards_url": "/flashcards.html",
            },
        )

    def save_runtime_article(self, article: dict, overwrite: bool) -> tuple[dict, Path]:
        """Persist a validated article while retaining the current store's rollback behaviour."""
        RUNTIME_ARTICLE_CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        target_path = article_store.article_storage_path(article, RUNTIME_ARTICLE_CONTENT_DIR)

        repo_conflict = next(
            (
                existing
                for existing in article_store.read_repo_article_specs()
                if existing["id"] == article["id"] or existing["file"] == article["file"]
            ),
            None,
        )
        if repo_conflict:
            raise ValueError("Article id or file conflicts with a repo-backed article.")

        existing_external = next(
            (
                existing
                for existing in article_store.read_external_article_specs(RUNTIME_ARTICLE_CONTENT_DIR)
                if existing["id"] == article["id"] or existing["file"] == article["file"]
            ),
            None,
        )
        if existing_external and not overwrite:
            raise ValueError("Runtime article already exists. Pass overwrite=true to replace it.")

        prior_bytes = target_path.read_bytes() if target_path.exists() else None
        temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        temp_path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(target_path)
        try:
            return self.validate_runtime_article_set(article["id"]), target_path
        except Exception:
            if prior_bytes is None:
                target_path.unlink(missing_ok=True)
            else:
                target_path.write_bytes(prior_bytes)
            raise

    def handle_article_agent_publish(self) -> None:
        """Draft an article with the selected configured agent, then publish it."""
        try:
            payload = self.read_json_body()
            brief = str(payload.get("brief", "")).strip()
            provider = str(payload.get("provider", "codex")).strip().lower()
            if provider not in {"codex", "deepseek"}:
                raise ValueError("Unsupported publishing agent.")
            if not brief:
                raise ValueError("Tell the publishing agent what article to create or revise.")
            if len(brief) > MAX_AGENT_BRIEF_CHARS:
                raise ValueError(f"Article brief is too long. Limit is {MAX_AGENT_BRIEF_CHARS:,} characters.")

            article_id = str(payload.get("article_id", "")).strip()
            existing_article = None
            if article_id:
                existing_article, _ = article_store.read_external_article_spec(
                    article_id, RUNTIME_ARTICLE_CONTENT_DIR
                )

            article = self.run_article_agent(provider, brief, existing_article)
            try:
                article_store.validate_article_payload(article, enforce_runtime_rules=True)
            except ValueError as validation_error:
                article = self.run_article_agent(
                    provider,
                    brief,
                    existing_article,
                    rejected_article=article,
                    validation_error=str(validation_error),
                )
                article_store.validate_article_payload(article, enforce_runtime_rules=True)
            saved, target_path = self.save_runtime_article(article, overwrite=existing_article is not None)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return
        except subprocess.TimeoutExpired:
            self.send_json(504, {"ok": False, "error": f"{provider.title()} took longer than five minutes. Please try again."})
            return
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": f"{provider.title()} article publish failed: {exc}"})
            return

        self.send_json(
            201,
            {
                "ok": True,
                "article": {"id": saved["id"], "file": saved["file"], "title": saved["title"], "href": generate_site.article_href(saved), "json_path": str(target_path)},
                "content_dir": str(RUNTIME_ARTICLE_CONTENT_DIR),
            },
        )

    def run_article_agent(
        self,
        provider: str,
        brief: str,
        existing_article: dict | None,
        rejected_article: dict | None = None,
        validation_error: str = "",
    ) -> dict:
        if provider == "deepseek":
            return self.run_deepseek_article_agent(brief, existing_article, rejected_article, validation_error)
        return self.run_codex_article_agent(brief, existing_article, rejected_article, validation_error)

    def article_agent_prompt(
        self,
        brief: str,
        existing_article: dict | None,
        rejected_article: dict | None = None,
        validation_error: str = "",
    ) -> str:
        existing_context = (
            "This is a revision. Preserve its id, file, date, month, navLabel, and downloadFileName unless the brief explicitly asks otherwise.\n"
            f"Existing article:\n{json.dumps(existing_article, ensure_ascii=False, indent=2)}"
            if existing_article else "Create a new article with a date-based id and matching file name."
        )
        correction_context = (
            "Your first draft was rejected by the runtime validator. Correct it completely and return a replacement article object. "
            "Preserve its identity fields unless the validator error requires otherwise.\n"
            f"Validator error: {validation_error}\n"
            f"Rejected draft:\n{json.dumps(rejected_article, ensure_ascii=False, indent=2)}"
            if rejected_article else ""
        )
        return f'''You are the publishing agent for a Japanese reading site. Produce one complete runtime article object from the brief below. You may research a supplied source URL if needed, but do not modify files or run shell commands. Your final response must be the article object alone and must satisfy the schema.

Article requirements:
- include id, file, title, titleTranslation, date, month, navLabel, level, downloadFileName, headlineHtml, sourceNote, paragraphs, vocabularyTitle, vocabulary
- downloadFileName must be a plain MP4 filename ending in .mp4; use the article id followed by .mp4
- month must be an English archive label such as "July 2026", never a machine-style value such as "2026-07"
- paragraphs has exactly 5 objects, each with html and an accurate English translation
- each html has 1-3 Japanese sentences; the visible Japanese text across all five is 450-500 characters
- put every kanji in headlineHtml and body html inside ruby markup with a kana reading; vocabulary items have term and meaning
- keep the article factual, clear, compact, and suitable for Japanese learners
- before responding, remove ruby markup mentally and count the visible Japanese body text; do not respond unless it is 450-500 characters
- return JSON only, without markdown fences or commentary

{existing_context}

{correction_context}

User brief:
{brief}'''

    def article_agent_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["id", "file", "title", "titleTranslation", "date", "month", "navLabel", "level", "downloadFileName", "headlineHtml", "sourceNote", "paragraphs", "vocabularyTitle", "vocabulary"],
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string"}, "file": {"type": "string"}, "title": {"type": "string"}, "titleTranslation": {"type": "string"}, "date": {"type": "string"}, "month": {"type": "string"}, "navLabel": {"type": "string"}, "level": {"type": "string"}, "downloadFileName": {"type": "string"}, "headlineHtml": {"type": "string"}, "sourceNote": {"type": "string"}, "vocabularyTitle": {"type": "string"},
                "paragraphs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["html", "translation"],
                        "properties": {"html": {"type": "string"}, "translation": {"type": "string"}},
                    },
                },
                "vocabulary": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["term", "meaning"],
                        "properties": {"term": {"type": "string"}, "meaning": {"type": "string"}},
                    },
                },
            },
        }

    def run_codex_article_agent(
        self,
        brief: str,
        existing_article: dict | None,
        rejected_article: dict | None = None,
        validation_error: str = "",
    ) -> dict:
        codex_bin = shutil.which("codex")
        if not codex_bin:
            raise ValueError("Codex CLI is not installed or not on PATH for the server.")
        prompt = self.article_agent_prompt(brief, existing_article, rejected_article, validation_error)
        schema = self.article_agent_schema()
        with tempfile.TemporaryDirectory(prefix="learn-japanese-codex-") as temp_dir:
            schema_path = Path(temp_dir) / "article-schema.json"
            output_path = Path(temp_dir) / "article.json"
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            result = subprocess.run(
                [codex_bin, "exec", "--model", CODEX_ARTICLE_AGENT_MODEL, "--ephemeral", "--sandbox", "read-only", "--cd", str(PROJECT_DIR), "--output-schema", str(schema_path), "--output-last-message", str(output_path), prompt],
                capture_output=True, text=True, timeout=CODEX_AGENT_TIMEOUT_SECONDS, check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "Codex did not return a result.").strip()
                raise RuntimeError(detail[-1200:])
            if not output_path.exists():
                raise RuntimeError("Codex finished without an article response.")
            article = json.loads(output_path.read_text(encoding="utf-8"))
        if not isinstance(article, dict):
            raise ValueError("Codex returned an invalid article object.")
        return article

    def run_deepseek_article_agent(
        self,
        brief: str,
        existing_article: dict | None,
        rejected_article: dict | None = None,
        validation_error: str = "",
    ) -> dict:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DeepSeek is not configured. Set DEEPSEEK_API_KEY on the server and restart it.")
        prompt = self.article_agent_prompt(brief, existing_article, rejected_article, validation_error)
        body = json.dumps({
            "model": DEEPSEEK_AGENT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }).encode("utf-8")
        request = urlrequest.Request(
            DEEPSEEK_API_URL,
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=CODEX_AGENT_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urlerror.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}: {detail[-800:]}") from exc
        except urlerror.URLError as exc:
            raise RuntimeError(f"Could not reach the DeepSeek API: {exc.reason}") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
            article = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("DeepSeek returned an invalid article response.") from exc
        if not isinstance(article, dict):
            raise ValueError("DeepSeek returned an invalid article object.")
        return article

    def handle_article_delete(self, query_string: str) -> None:
        params = parse.parse_qs(query_string, keep_blank_values=False)
        article_ref = str(params.get("article_id", [""])[0]).strip()
        if not article_ref:
            self.send_json(400, {"ok": False, "error": "Missing article_id query parameter."})
            return

        try:
            article, target_path = article_store.read_external_article_spec(
                article_ref, RUNTIME_ARTICLE_CONTENT_DIR
            )
            prior_bytes = target_path.read_bytes()
            target_path.unlink()
            try:
                articles = self.runtime_articles()
                generate_site.render_index_html(articles)
                generate_site.build_flashcards_payload(articles)
            except Exception:
                target_path.write_bytes(prior_bytes)
                raise
        except ValueError as exc:
            self.send_json(404, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": f"Runtime article delete failed: {exc}"})
            return

        self.send_json(
            200,
            {
                "ok": True,
                "deleted": {
                    "id": article["id"],
                    "file": article["file"],
                    "json_path": str(target_path),
                },
                "content_dir": str(RUNTIME_ARTICLE_CONTENT_DIR),
            },
        )

    def handle_articles_backup(self) -> None:
        if not RUNTIME_ARTICLE_CONTENT_DIR.exists():
            self.send_json(
                404,
                {"ok": False, "error": "Runtime content directory does not exist yet."},
            )
            return

        with tempfile.TemporaryDirectory(prefix="learn-japanese-backup-") as temp_dir:
            archive_base = Path(temp_dir) / "learn-japanese-runtime-content"
            archive_path = Path(
                shutil.make_archive(
                    str(archive_base),
                    "zip",
                    root_dir=str(RUNTIME_ARTICLE_CONTENT_DIR),
                )
            )
            archive_bytes = archive_path.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(archive_bytes)))
        self.send_header(
            "Content-Disposition",
            'attachment; filename="learn-japanese-runtime-content.zip"',
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(archive_bytes)

    def handle_voicevox_status(self) -> None:
        try:
            speakers = voicevox_request("GET", "/speakers", base_url=VOICEVOX_BASE_URL)
        except VoicevoxRequestError as exc:
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

    def default_voice_settings(self) -> dict:
        return {
            "schemaVersion": 1,
            "source": "docker",
            "browserVoice": "Google 日本語",
            "browserRate": 0.9,
            "browserPitch": 1.0,
            "dockerSpeaker": DEFAULT_VOICEVOX_SPEAKER,
            "voicevoxProsody": dict(DEFAULT_VOICEVOX_PROSODY),
        }

    def normalize_voice_setting_number(
        self,
        value: object,
        *,
        fallback: float,
        minimum: float,
        maximum: float,
    ) -> float:
        if value is None or value == "":
            return fallback
        normalized = float(value)
        if normalized < minimum or normalized > maximum:
            raise ValueError(f"Value must be between {minimum} and {maximum}.")
        return round(normalized, 2)

    def normalize_voice_settings(self, payload: dict | None = None) -> dict:
        defaults = self.default_voice_settings()
        source_payload = payload if isinstance(payload, dict) else {}
        source = str(source_payload.get("source", defaults["source"])).strip()
        if source not in {"browser", "docker"}:
            raise ValueError("Voice source must be browser or docker.")

        browser_voice = str(source_payload.get("browserVoice", defaults["browserVoice"])).strip() or defaults["browserVoice"]
        docker_speaker = int(source_payload.get("dockerSpeaker", defaults["dockerSpeaker"]))
        if docker_speaker < 0:
            raise ValueError("Docker speaker must be a non-negative integer.")

        browser_rate = self.normalize_voice_setting_number(
            source_payload.get("browserRate", defaults["browserRate"]),
            fallback=defaults["browserRate"],
            minimum=0.7,
            maximum=1.2,
        )
        browser_pitch = self.normalize_voice_setting_number(
            source_payload.get("browserPitch", defaults["browserPitch"]),
            fallback=defaults["browserPitch"],
            minimum=0.8,
            maximum=1.3,
        )
        prosody_payload = source_payload.get("voicevoxProsody", {})
        if prosody_payload is None:
            prosody_payload = {}
        if not isinstance(prosody_payload, dict):
            raise ValueError("VOICEVOX prosody must be an object.")
        voicevox_prosody = {
            "speedScale": self.normalize_voice_setting_number(
                prosody_payload.get("speedScale", defaults["voicevoxProsody"]["speedScale"]),
                fallback=defaults["voicevoxProsody"]["speedScale"],
                minimum=0.8,
                maximum=1.2,
            ),
            "pitchScale": self.normalize_voice_setting_number(
                prosody_payload.get("pitchScale", defaults["voicevoxProsody"]["pitchScale"]),
                fallback=defaults["voicevoxProsody"]["pitchScale"],
                minimum=-0.12,
                maximum=0.12,
            ),
            "intonationScale": self.normalize_voice_setting_number(
                prosody_payload.get("intonationScale", defaults["voicevoxProsody"]["intonationScale"]),
                fallback=defaults["voicevoxProsody"]["intonationScale"],
                minimum=0.7,
                maximum=1.6,
            ),
        }
        return {
            "schemaVersion": defaults["schemaVersion"],
            "source": source,
            "browserVoice": browser_voice,
            "browserRate": browser_rate,
            "browserPitch": browser_pitch,
            "dockerSpeaker": docker_speaker,
            "voicevoxProsody": normalize_voicevox_prosody(voicevox_prosody),
        }

    def read_voice_settings(self) -> dict:
        if not VOICE_SETTINGS_PATH.exists():
            return self.default_voice_settings()
        payload = json.loads(VOICE_SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Voice settings file must contain a JSON object.")
        return self.normalize_voice_settings(payload)

    def write_voice_settings(self, settings: dict) -> None:
        VOICE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = VOICE_SETTINGS_PATH.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(VOICE_SETTINGS_PATH)

    def current_voice_settings(self) -> dict:
        with VOICE_SETTINGS_LOCK:
            return self.read_voice_settings()

    def resolve_voicevox_request_settings(self, payload: dict) -> tuple[int, dict]:
        settings = self.current_voice_settings()
        speaker_value = payload.get("speaker")
        speaker = int(speaker_value) if speaker_value is not None else int(settings["dockerSpeaker"])
        if speaker < 0:
            raise ValueError("Docker speaker must be a non-negative integer.")

        prosody_source = payload.get("voicevoxProsody")
        if prosody_source is None:
            prosody_source = settings.get("voicevoxProsody", {})
        if not isinstance(prosody_source, dict):
            raise ValueError("VOICEVOX prosody must be an object.")

        defaults = settings.get("voicevoxProsody", self.default_voice_settings()["voicevoxProsody"])
        prosody = {
            "speedScale": self.normalize_voice_setting_number(
                prosody_source.get("speedScale", defaults["speedScale"]),
                fallback=defaults["speedScale"],
                minimum=0.8,
                maximum=1.2,
            ),
            "pitchScale": self.normalize_voice_setting_number(
                prosody_source.get("pitchScale", defaults["pitchScale"]),
                fallback=defaults["pitchScale"],
                minimum=-0.12,
                maximum=0.12,
            ),
            "intonationScale": self.normalize_voice_setting_number(
                prosody_source.get("intonationScale", defaults["intonationScale"]),
                fallback=defaults["intonationScale"],
                minimum=0.7,
                maximum=1.6,
            ),
        }
        return speaker, normalize_voicevox_prosody(prosody)

    def render_options_for_speaker(self, article_id: str, speaker: int, prosody: dict) -> RenderOptions:
        return RenderOptions(
            article_id=article_id,
            speaker=speaker,
            voicevox_speed_scale=prosody["speedScale"],
            voicevox_pitch_scale=prosody["pitchScale"],
            voicevox_intonation_scale=prosody["intonationScale"],
        )

    def handle_voice_settings_get(self) -> None:
        try:
            settings = self.current_voice_settings()
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json(500, {"ok": False, "error": f"Voice settings could not be loaded: {exc}"})
            return

        self.send_json(200, {"ok": True, "settings": settings})

    def handle_voice_settings_update(self) -> None:
        try:
            payload = self.read_json_body()
        except (TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": f"Invalid JSON request: {exc}"})
            return

        try:
            with VOICE_SETTINGS_LOCK:
                current = self.read_voice_settings()
                merged = dict(current)
                merged.update({key: value for key, value in payload.items() if key != "voicevoxProsody"})
                current_prosody = dict(current.get("voicevoxProsody", {}))
                next_prosody = payload.get("voicevoxProsody")
                if next_prosody is not None:
                    if not isinstance(next_prosody, dict):
                        raise ValueError("VOICEVOX prosody must be an object.")
                    current_prosody.update(next_prosody)
                merged["voicevoxProsody"] = current_prosody
                settings = self.normalize_voice_settings(merged)
                self.write_voice_settings(settings)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return

        self.send_json(200, {"ok": True, "settings": settings})

    def handle_video_preview(self, query_string: str) -> None:
        params = parse.parse_qs(query_string, keep_blank_values=False)
        article_ref = str(params.get("article_id", [""])[0]).strip()
        if not article_ref:
            self.send_json(400, {"ok": False, "error": "Missing article_id query parameter."})
            return

        try:
            article = article_store.find_article(article_ref, RUNTIME_ARTICLE_CONTENT_DIR)
            segment = build_segments(article)[0]
            html = render_html(article, segment, RenderOptions(article_id=article["id"]))
        except (ValueError, IndexError) as exc:
            self.send_json(404, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": f"Preview render failed: {exc}"})
            return

        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def handle_voicevox_synthesis(self) -> None:
        try:
            payload = self.read_json_body()
            text = str(payload.get("text", "")).strip()
            speaker, prosody = self.resolve_voicevox_request_settings(payload)
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
            wav_audio, cache_hit, cache_file = cached_voicevox_wav(
                text,
                speaker,
                base_url=VOICEVOX_BASE_URL,
                prosody=prosody,
            )
        except VoicevoxRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return

        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(wav_audio)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("X-Audio-Cache", "hit" if cache_hit else "miss")
        self.send_header("X-Audio-Cache-Key", cache_file.stem)
        self.end_headers()
        self.wfile.write(wav_audio)

    def handle_voicevox_cache_status(self) -> None:
        try:
            payload = self.read_json_body()
            raw_texts = payload.get("texts")
            if raw_texts is None:
                raw_texts = [payload.get("text", "")]
            if not isinstance(raw_texts, list):
                raise TypeError("texts must be an array")
            speaker, prosody = self.resolve_voicevox_request_settings(payload)
            texts = [str(text).strip() for text in raw_texts]
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": f"Invalid JSON request: {exc}"})
            return

        if len(texts) > 100:
            self.send_json(413, {"ok": False, "error": "Too many texts. Limit is 100."})
            return

        results = []
        cached_count = 0
        for index, text in enumerate(texts):
            if not text:
                results.append({"index": index, "cached": False, "cache": "missing", "key": ""})
                continue
            if len(text) > MAX_TTS_TEXT_CHARS:
                self.send_json(
                    413,
                    {
                        "ok": False,
                        "error": f"Text is too long. Limit is {MAX_TTS_TEXT_CHARS} characters.",
                    },
                )
                return
            path = cache_path(text, speaker, prosody=prosody)
            cached = path.exists()
            if cached:
                cached_count += 1
            results.append(
                {
                    "index": index,
                    "cached": cached,
                    "cache": "hit" if cached else "miss",
                    "key": path.stem,
                }
            )

        self.send_json(
            200,
            {
                "ok": True,
                "speaker": speaker,
                "voicevoxProsody": prosody,
                "cached": cached_count,
                "missing": len(results) - cached_count,
                "results": results,
            },
        )

    def handle_flashcard_progress_get(self) -> None:
        try:
            with FLASHCARD_PROGRESS_LOCK:
                progress = self.read_flashcard_progress()
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json(500, {"ok": False, "error": f"Progress could not be loaded: {exc}"})
            return
        self.send_json(200, {"ok": True, **progress})

    def handle_flashcard_progress_update(self) -> None:
        try:
            payload = self.read_json_body()
            operation = str(payload.get("operation", "")).strip()
        except (TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": f"Invalid JSON request: {exc}"})
            return

        try:
            with FLASHCARD_PROGRESS_LOCK:
                progress = self.read_flashcard_progress()
                if operation == "put":
                    store = self.progress_store_name(payload)
                    record = self.progress_record(payload)
                    progress[store] = self.upsert_progress_record(store, progress[store], record)
                elif operation == "add":
                    store = self.progress_store_name(payload)
                    record = self.progress_record(payload)
                    progress[store] = self.upsert_progress_record(store, progress[store], record)
                elif operation == "clear":
                    store = self.progress_store_name(payload)
                    progress[store] = []
                elif operation == "replace":
                    progress["cards"] = self.progress_record_list(payload.get("cards", []))
                    progress["reviews"] = self.progress_record_list(payload.get("reviews", []))
                elif operation == "reset":
                    progress["cards"] = []
                    progress["reviews"] = []
                else:
                    raise ValueError("Unsupported progress operation.")

                self.write_flashcard_progress(progress)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return

        self.send_json(200, {"ok": True, **progress})

    def read_flashcard_progress(self) -> dict:
        if not FLASHCARD_PROGRESS_PATH.exists():
            return {"schemaVersion": 2, "cards": [], "reviews": []}

        payload = json.loads(FLASHCARD_PROGRESS_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Progress file must contain a JSON object.")

        cards = self.progress_record_list(payload.get("cards", []))
        reviews = self.progress_record_list(payload.get("reviews", []))
        return {"schemaVersion": 2, "cards": cards, "reviews": reviews}

    def write_flashcard_progress(self, progress: dict) -> None:
        FLASHCARD_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = FLASHCARD_PROGRESS_PATH.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(FLASHCARD_PROGRESS_PATH)

    def progress_store_name(self, payload: dict) -> str:
        store = str(payload.get("store", "")).strip()
        if store not in {"cards", "reviews"}:
            raise ValueError("Progress store must be cards or reviews.")
        return store

    def progress_record(self, payload: dict) -> dict:
        record = payload.get("record")
        if not isinstance(record, dict):
            raise ValueError("Progress record must be an object.")
        return record

    def progress_record_list(self, value: object) -> list[dict]:
        if not isinstance(value, list):
            raise ValueError("Progress records must be an array.")
        if not all(isinstance(item, dict) for item in value):
            raise ValueError("Each progress record must be an object.")
        return value

    def upsert_progress_record(self, store: str, records: list[dict], record: dict) -> list[dict]:
        key = "card_id" if store == "cards" else "id"
        record_id = str(record.get(key, "")).strip()
        if not record_id:
            raise ValueError(f"Progress record is missing {key}.")

        updated = False
        next_records = []
        for existing in records:
            if str(existing.get(key, "")).strip() == record_id:
                next_records.append(
                    self.merge_card_progress(existing, record) if store == "cards" else record
                )
                updated = True
            else:
                next_records.append(existing)
        if not updated:
            next_records.append(record)
        return next_records

    def merge_card_progress(self, existing: dict, incoming: dict) -> dict:
        merged = {**existing, **incoming}
        for key in ("shown_count", "remembered_count", "forgot_count"):
            merged[key] = max(int(existing.get(key) or 0), int(incoming.get(key) or 0))

        for key in ("last_shown_at", "last_answered_at"):
            merged[key] = max(str(existing.get(key) or ""), str(incoming.get(key) or "")) or None

        existing_answered = str(existing.get("last_answered_at") or "")
        incoming_answered = str(incoming.get("last_answered_at") or "")
        schedule_source = incoming if incoming_answered >= existing_answered else existing
        for key in ("due_at", "interval_days", "ease_factor", "state"):
            merged[key] = schedule_source.get(key)

        return merged

    def handle_mp4_conversion(self) -> None:
        if not shutil.which("ffmpeg"):
            self.send_json(503, {"ok": False, "error": "ffmpeg is not installed or not on PATH."})
            return

        try:
            source_video = self.read_binary_body(MAX_VIDEO_UPLOAD_BYTES)
        except ValueError as exc:
            self.send_json(413, {"ok": False, "error": str(exc)})
            return

        if not source_video:
            self.send_json(400, {"ok": False, "error": "Missing video data."})
            return

        try:
            with tempfile.TemporaryDirectory(prefix="learn-japanese-video-") as temp_dir:
                temp_path = Path(temp_dir)
                input_path = temp_path / "input.webm"
                output_path = temp_path / "output.mp4"
                input_path.write_bytes(source_video)

                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(input_path),
                        "-vf",
                        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        "veryfast",
                        "-movflags",
                        "+faststart",
                        "-af",
                        EXPORT_AUDIO_FILTER,
                        "-c:a",
                        "aac",
                        "-b:a",
                        "160k",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                )
                mp4_video = output_path.read_bytes()
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
            self.send_json(500, {"ok": False, "error": f"ffmpeg conversion failed: {detail}"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(mp4_video)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(mp4_video)

    def handle_video_render(self) -> None:
        try:
            article, output_path, temp_dir = self.render_video_to_temp_file()
            try:
                mp4_video = output_path.read_bytes()
            finally:
                temp_dir.cleanup()
        except VideoRenderRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return

        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(mp4_video)))
        self.send_header("Content-Disposition", f'attachment; filename="{article["downloadFileName"]}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(mp4_video)

    def handle_video_render_url(self) -> None:
        try:
            VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            payload = self.read_json_body()
            article_id = str(payload.get("article_id", "")).strip()
            speaker, prosody = self.resolve_voicevox_request_settings(payload)
            if not article_id:
                raise VideoRenderRequestError(400, "Missing article_id.")
            try:
                article = article_store.find_article(article_id, RUNTIME_ARTICLE_CONTENT_DIR)
            except ValueError as exc:
                raise VideoRenderRequestError(404, str(exc)) from exc

            output_path = VIDEO_OUTPUT_DIR / article["downloadFileName"]
            cache_key = self.video_render_cache_key(article, speaker, prosody)
            if self.video_render_cache_matches(output_path, cache_key):
                version = str(output_path.stat().st_mtime_ns)
            else:
                temp_dir = tempfile.TemporaryDirectory(prefix="learn-japanese-render-")
                temp_output_path = Path(temp_dir.name) / article["downloadFileName"]
                try:
                    options = self.render_options_for_speaker(article["id"], speaker, prosody)
                    render_article_video(article, temp_output_path, options, DEFAULT_VOICEVOX_TIMEOUT)
                    shutil.move(str(temp_output_path), str(output_path))
                    self.write_video_render_cache_key(output_path, cache_key)
                    version = str(output_path.stat().st_mtime_ns)
                finally:
                    temp_dir.cleanup()
        except VideoRenderRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": f"Invalid JSON request: {exc}"})
            return
        except SystemExit as exc:
            message = str(exc)
            status = 503 if "VOICEVOX" in message or "Chromium" in message or "ffmpeg" in message else 500
            self.send_json(status, {"ok": False, "error": message})
            return
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace").strip() if exc.stderr else str(exc)
            self.send_json(500, {"ok": False, "error": f"Video render failed: {detail}"})
            return

        self.send_json(
            200,
            {
                "ok": True,
                "article_id": article["id"],
                "filename": article["downloadFileName"],
                "download_url": self.build_download_url(article["downloadFileName"], version),
            },
        )

    def handle_video_cover_render(self) -> None:
        try:
            article, cover_path, temp_dir = self.render_article_cover_to_temp_file()
            try:
                cover_image = cover_path.read_bytes()
            finally:
                temp_dir.cleanup()
        except VideoRenderRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return

        filename = video_cover_filename(article["downloadFileName"])
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(cover_image)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cover_image)

    def handle_quiz_video_render_url(self) -> None:
        try:
            quiz, speaker, prosody = self.parse_quiz_video_request()
            VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            filename = quiz_video_filename(quiz["id"])
            output_path = VIDEO_OUTPUT_DIR / filename
            cache_key = self.video_render_cache_key(quiz, speaker, prosody)
            if self.video_render_cache_matches(output_path, cache_key):
                version = str(output_path.stat().st_mtime_ns)
            else:
                temp_dir = tempfile.TemporaryDirectory(prefix="learn-japanese-quiz-render-")
                temp_output_path = Path(temp_dir.name) / filename
                try:
                    options = self.render_options_for_speaker(quiz["id"], speaker, prosody)
                    render_quiz_video(quiz, temp_output_path, options)
                    shutil.move(str(temp_output_path), str(output_path))
                    self.write_video_render_cache_key(output_path, cache_key)
                    version = str(output_path.stat().st_mtime_ns)
                finally:
                    temp_dir.cleanup()
        except VideoRenderRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return
        except SystemExit as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})
            return
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace").strip() if exc.stderr else str(exc)
            self.send_json(500, {"ok": False, "error": f"Quiz video render failed: {detail}"})
            return

        self.send_json(
            200,
            {
                "ok": True,
                "quiz_id": quiz["id"],
                "filename": filename,
                "download_url": self.build_download_url(filename, version),
            },
        )

    def handle_quiz_video_cover_render(self) -> None:
        try:
            quiz, _speaker, _prosody = self.parse_quiz_video_request()
            temp_dir = tempfile.TemporaryDirectory(prefix="learn-japanese-quiz-cover-")
            filename = video_cover_filename(quiz_video_filename(quiz["id"]))
            cover_path = Path(temp_dir.name) / filename
            try:
                options = RenderOptions(article_id=quiz["id"])
                render_quiz_cover(quiz, cover_path, options)
                cover_image = cover_path.read_bytes()
            finally:
                temp_dir.cleanup()
        except VideoRenderRequestError as exc:
            self.send_json(exc.status, {"ok": False, "error": exc.message})
            return
        except SystemExit as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})
            return
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace").strip() if exc.stderr else str(exc)
            self.send_json(500, {"ok": False, "error": f"Quiz cover render failed: {detail}"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(cover_image)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cover_image)

    def parse_quiz_video_request(self) -> tuple[dict, int, dict]:
        try:
            payload = self.read_json_body()
            quiz_id = str(payload.get("quiz_id", "")).strip()
            speaker, prosody = self.resolve_voicevox_request_settings(payload)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise VideoRenderRequestError(400, f"Invalid JSON request: {exc}") from exc

        if not quiz_id:
            raise VideoRenderRequestError(400, "Missing quiz_id.")

        try:
            return find_video_quiz(quiz_id), speaker, prosody
        except ValueError as exc:
            raise VideoRenderRequestError(404, str(exc)) from exc

    def render_video_to_temp_file(self) -> tuple[dict, Path, tempfile.TemporaryDirectory]:
        try:
            payload = self.read_json_body()
            article_id = str(payload.get("article_id", "")).strip()
            speaker, prosody = self.resolve_voicevox_request_settings(payload)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise VideoRenderRequestError(400, f"Invalid JSON request: {exc}") from exc

        if not article_id:
            raise VideoRenderRequestError(400, "Missing article_id.")

        try:
            article = article_store.find_article(article_id, RUNTIME_ARTICLE_CONTENT_DIR)
        except ValueError as exc:
            raise VideoRenderRequestError(404, str(exc)) from exc

        options = self.render_options_for_speaker(article["id"], speaker, prosody)

        temp_dir = None
        try:
            temp_dir = tempfile.TemporaryDirectory(prefix="learn-japanese-render-")
            temp_path = Path(temp_dir.name)
            output_path = temp_path / article["downloadFileName"]
            render_article_video(article, output_path, options, DEFAULT_VOICEVOX_TIMEOUT)
            return article, output_path, temp_dir
        except SystemExit as exc:
            if temp_dir:
                temp_dir.cleanup()
            message = str(exc)
            status = 503 if "VOICEVOX" in message or "Chromium" in message or "ffmpeg" in message else 500
            raise VideoRenderRequestError(status, message) from exc
        except subprocess.CalledProcessError as exc:
            if temp_dir:
                temp_dir.cleanup()
            detail = exc.stderr.decode("utf-8", errors="replace").strip() if exc.stderr else str(exc)
            raise VideoRenderRequestError(500, f"Video render failed: {detail}") from exc

    def render_article_cover_to_temp_file(self) -> tuple[dict, Path, tempfile.TemporaryDirectory]:
        try:
            payload = self.read_json_body()
            article_id = str(payload.get("article_id", "")).strip()
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise VideoRenderRequestError(400, f"Invalid JSON request: {exc}") from exc

        if not article_id:
            raise VideoRenderRequestError(400, "Missing article_id.")

        try:
            article = article_store.find_article(article_id, RUNTIME_ARTICLE_CONTENT_DIR)
        except ValueError as exc:
            raise VideoRenderRequestError(404, str(exc)) from exc

        temp_dir = None
        try:
            temp_dir = tempfile.TemporaryDirectory(prefix="learn-japanese-cover-")
            cover_path = Path(temp_dir.name) / video_cover_filename(article["downloadFileName"])
            render_article_cover(article, cover_path, RenderOptions(article_id=article["id"]))
            return article, cover_path, temp_dir
        except SystemExit as exc:
            if temp_dir:
                temp_dir.cleanup()
            message = str(exc)
            status = 503 if "Chromium" in message else 500
            raise VideoRenderRequestError(status, message) from exc
        except subprocess.CalledProcessError as exc:
            if temp_dir:
                temp_dir.cleanup()
            detail = exc.stderr.decode("utf-8", errors="replace").strip() if exc.stderr else str(exc)
            raise VideoRenderRequestError(500, f"Cover render failed: {detail}") from exc

    def build_download_url(self, filename: str, version: str | None = None) -> str:
        host = self.headers.get("Host") or f"{DEFAULT_PUBLIC_HOST}:{DEFAULT_PORT}"
        proto = self.headers.get("X-Forwarded-Proto", "http").split(",", 1)[0].strip() or "http"
        url = f"{proto}://{host}/videos/{parse.quote(filename)}"
        if version:
            url = f"{url}?v={parse.quote(version)}"
        return url

    def video_render_cache_metadata_path(self, output_path: Path) -> Path:
        return output_path.with_suffix(f"{output_path.suffix}.cache.json")

    def video_render_cache_key(self, payload: dict, speaker: int, prosody: dict) -> str:
        encoded = json.dumps(
            {
                "version": "video-render-v8",
                "speaker": speaker,
                "voicevoxProsody": prosody,
                "payload": payload,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def video_render_cache_matches(self, output_path: Path, cache_key: str) -> bool:
        if not output_path.exists():
            return False

        metadata_path = self.video_render_cache_metadata_path(output_path)
        if not metadata_path.exists():
            return False

        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False

        return payload.get("cache_key") == cache_key

    def write_video_render_cache_key(self, output_path: Path, cache_key: str) -> None:
        metadata_path = self.video_render_cache_metadata_path(output_path)
        metadata_path.write_text(
            json.dumps({"cache_key": cache_key}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        if not raw_body:
            return {}

        value = json.loads(raw_body.decode("utf-8"))
        if not isinstance(value, dict):
            raise TypeError("JSON body must be an object")

        return value

    def read_binary_body(self, max_bytes: int) -> bytes:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > max_bytes:
            raise ValueError(f"Video is too large. Limit is {max_bytes // (1024 * 1024)} MB.")

        return self.rfile.read(content_length)

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class VideoRenderRequestError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def public_site_url(host: str, port: int) -> str:
    public_host = DEFAULT_PUBLIC_HOST if host in {"0.0.0.0", "::"} else host
    return f"http://{public_host}:{port}/index.html"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve static learn-japanese pages for browser-based study and recording."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), LearnJapaneseHandler)
    print(f"Open {public_site_url(args.host, args.port)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
