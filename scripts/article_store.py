from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ARTICLES_PATH = ROOT / "data" / "articles.json"
DEFAULT_CONTENT_DIR = Path(
    os.environ.get(
        "CONTENT_DIR",
        str(Path.home() / ".local" / "share" / "learn-japanese" / "articles"),
    )
)


def content_dir() -> Path:
    return DEFAULT_CONTENT_DIR


def article_version_label(article: dict) -> str:
    return article.get("versionLabel") or article.get("level") or "Original"


def variant_slug(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return slug or "version"


def variant_file(base_file: str, label: str) -> str:
    path = Path(base_file)
    return f"{path.stem}-{variant_slug(label)}{path.suffix}"


def variant_id(base_id: str, label: str) -> str:
    return f"{base_id}-{variant_slug(label)}"


def variant_download_file_name(base_download_file_name: str, label: str) -> str:
    path = Path(base_download_file_name)
    return f"{path.stem}-{variant_slug(label)}{path.suffix}"


def article_href(article: dict) -> str:
    return f"./{article['file']}"


def html_base_text(html: str) -> str:
    text = re.sub(r"<rt>.*?</rt>|<rp>.*?</rp>", "", html, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    matches = re.findall(r"[^。！？!?]+[。！？!?]?", text)
    sentences = [match.strip() for match in matches if match.strip()]
    return sentences or ([text.strip()] if text.strip() else [])


def expand_article_versions(article: dict) -> list[dict]:
    version_specs = article.get("versions", [])
    base = deepcopy(article)
    base.pop("versions", None)
    base["canonicalId"] = article.get("canonicalId", article["id"])
    base["versionLabel"] = article_version_label(base)

    versions = [base]
    for spec in version_specs:
        version = deepcopy(base)
        version.update(deepcopy(spec))
        version["canonicalId"] = base["canonicalId"]
        version["versionLabel"] = article_version_label(version)
        if "id" not in spec:
            version["id"] = variant_id(base["id"], version["versionLabel"])
        if "file" not in spec:
            version["file"] = variant_file(base["file"], version["versionLabel"])
        if "downloadFileName" not in spec:
            version["downloadFileName"] = variant_download_file_name(
                base["downloadFileName"], version["versionLabel"]
            )
        if "navLabel" not in spec:
            version["navLabel"] = f"{base['navLabel']} {version['versionLabel']}"
        versions.append(version)

    variant_links = [
        {
            "href": article_href(version),
            "label": article_version_label(version),
            "level": version.get("level", ""),
        }
        for version in versions
    ]
    for version in versions:
        version["articleVersions"] = [
            link | {"current": link["href"] == article_href(version)}
            for link in variant_links
        ]
    return versions


def validate_article_payload(article: dict, enforce_runtime_rules: bool = False) -> None:
    if not isinstance(article, dict):
        raise ValueError("Article payload must be an object.")

    required_strings = [
        "id",
        "file",
        "title",
        "date",
        "month",
        "navLabel",
        "downloadFileName",
        "headlineHtml",
        "sourceNote",
        "vocabularyTitle",
    ]
    for key in required_strings:
        value = str(article.get(key, "")).strip()
        if not value:
            raise ValueError(f"Article is missing {key}.")

    article_id = str(article["id"]).strip()
    article_file = str(article["file"]).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+", article_id):
        raise ValueError("Article id must look like YYYY-MM-DD-slug.")
    if not article_file.endswith(".html"):
        raise ValueError("Article file must end with .html.")
    if article_file[:10] != article_id[:10]:
        raise ValueError("Article id and file must start with the same date.")

    paragraphs = article.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        raise ValueError("Article paragraphs must be a non-empty array.")
    for index, paragraph in enumerate(paragraphs, start=1):
        if not isinstance(paragraph, dict):
            raise ValueError(f"Paragraph {index} must be an object.")
        html = str(paragraph.get("html", "")).strip()
        if not html:
            raise ValueError(f"Paragraph {index} is missing html.")
        translation = paragraph.get("translation")
        if translation is not None and not str(translation).strip():
            raise ValueError(f"Paragraph {index} has an empty translation.")

    if enforce_runtime_rules:
        if len(paragraphs) != 5:
            raise ValueError("Runtime articles must have exactly 5 sections in paragraphs.")

        visible_body = []
        for index, paragraph in enumerate(paragraphs, start=1):
            text = html_base_text(str(paragraph.get("html", "")).strip())
            sentence_count = len(split_sentences(text))
            if sentence_count < 1 or sentence_count > 3:
                raise ValueError(
                    f"Section {index} must contain between 1 and 3 sentences. Found {sentence_count}."
                )
            visible_body.append(text)

        body_character_count = len(re.sub(r"\s+", "", "".join(visible_body)))
        if body_character_count < 450 or body_character_count > 500:
            raise ValueError(
                "Runtime articles must have 450-500 visible body characters across the 5 sections. "
                f"Found {body_character_count}."
            )

    vocabulary = article.get("vocabulary")
    if not isinstance(vocabulary, list):
        raise ValueError("Article vocabulary must be an array.")
    for index, item in enumerate(vocabulary, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Vocabulary item {index} must be an object.")
        term = str(item.get("term", "")).strip()
        meaning = str(item.get("meaning", "")).strip()
        if not term or not meaning:
            raise ValueError(f"Vocabulary item {index} needs term and meaning.")

    versions = article.get("versions", [])
    if versions is not None and not isinstance(versions, list):
        raise ValueError("Article versions must be an array when provided.")


def read_repo_article_specs() -> list[dict]:
    data = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    data_root = ARTICLES_PATH.parent.resolve()
    articles = []
    for article_path in data["articles"]:
        path = (data_root / article_path).resolve()
        if not path.is_relative_to(data_root):
            raise ValueError(f"Article path escapes data directory: {article_path}")
        article = json.loads(path.read_text(encoding="utf-8"))
        validate_article_payload(article)
        articles.append(article)
    return articles


def article_json_filename(article: dict) -> str:
    file_name = str(article["file"]).strip()
    if file_name.endswith(".html"):
        return f"{file_name[:-5]}.json"
    return f"{article['id']}.json"


def article_storage_path(article: dict, runtime_dir: Path | None = None) -> Path:
    directory = runtime_dir or content_dir()
    return directory / article_json_filename(article)


def read_external_article_spec(article_ref: str, runtime_dir: Path | None = None) -> tuple[dict, Path]:
    directory = runtime_dir or content_dir()
    normalized = article_ref.removesuffix(".json").removesuffix(".html")
    for path in sorted(directory.glob("*.json"), reverse=True):
        article = json.loads(path.read_text(encoding="utf-8"))
        validate_article_payload(article)
        candidates = {
            article["id"],
            article["file"],
            article["file"].removesuffix(".html"),
            path.name,
            path.stem,
        }
        if article_ref in candidates or normalized in candidates:
            return article, path
    raise ValueError(f"Runtime article not found: {article_ref}")


def read_external_article_specs(runtime_dir: Path | None = None) -> list[dict]:
    directory = runtime_dir or content_dir()
    if not directory.exists():
        return []

    articles = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        article = json.loads(path.read_text(encoding="utf-8"))
        validate_article_payload(article)
        articles.append(article)
    return articles


def merge_article_specs(
    repo_articles: list[dict],
    external_articles: list[dict],
) -> list[dict]:
    merged = []
    repo_index = 0
    external_index = 0

    while repo_index < len(repo_articles) or external_index < len(external_articles):
        repo_article = repo_articles[repo_index] if repo_index < len(repo_articles) else None
        external_article = (
            external_articles[external_index] if external_index < len(external_articles) else None
        )

        if repo_article is None:
            merged.append(external_article)
            external_index += 1
            continue

        if external_article is None:
            merged.append(repo_article)
            repo_index += 1
            continue

        repo_date = str(repo_article["file"])[:10]
        external_date = str(external_article["file"])[:10]
        if external_date >= repo_date:
            merged.append(external_article)
            external_index += 1
        else:
            merged.append(repo_article)
            repo_index += 1

    return merged


def load_article_specs(runtime_dir: Path | None = None) -> list[dict]:
    return merge_article_specs(read_repo_article_specs(), read_external_article_specs(runtime_dir))


def load_articles(runtime_dir: Path | None = None) -> list[dict]:
    articles = []
    for article in load_article_specs(runtime_dir):
        articles.extend(expand_article_versions(article))
    return articles


def find_article(article_ref: str, runtime_dir: Path | None = None) -> dict:
    normalized = article_ref.removesuffix(".json").removesuffix(".html")
    for article in load_articles(runtime_dir):
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
