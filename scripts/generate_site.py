#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from hashlib import sha1
from datetime import date
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ARTICLES_PATH = ROOT / "data" / "articles.json"
ARTICLE_TEMPLATE_PATH = ROOT / "templates" / "article.html"
ARTICLE_JS_PATH = ROOT / "assets" / "article.js"
INDEX_PATH = ROOT / "index.html"


def load_articles() -> list[dict]:
    data = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    data_root = ARTICLES_PATH.parent.resolve()
    articles = []
    for article_path in data["articles"]:
        path = (data_root / article_path).resolve()
        if not path.is_relative_to(data_root):
            raise ValueError(f"Article path escapes data directory: {article_path}")
        articles.append(json.loads(path.read_text(encoding="utf-8")))
    return articles


def article_href(article: dict) -> str:
    return f"./{article['file']}"


def article_slug(article: dict) -> str:
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", article["id"])


def article_iso_date(article: dict) -> str:
    return article["file"][:10]


def article_weekday(article: dict) -> str:
    return date.fromisoformat(article_iso_date(article)).strftime("%A")


def article_navigation(articles: list[dict]) -> list[dict]:
    return [
        {
            "month": article["month"],
            "href": article_href(article),
            "label": article["navLabel"],
        }
        for article in articles
    ]


def article_navigation_version(articles: list[dict]) -> str:
    nav_json = json.dumps(article_navigation(articles), ensure_ascii=False, sort_keys=True)
    return sha1(nav_json.encode("utf-8")).hexdigest()[:12]


def replace_article_navigation(articles: list[dict]) -> None:
    article_js = ARTICLE_JS_PATH.read_text(encoding="utf-8")
    nav_json = json.dumps(article_navigation(articles), ensure_ascii=False, indent=4)
    updated = re.sub(
        r"const articleNavigation = \[.*?\];",
        f"const articleNavigation = {nav_json};",
        article_js,
        count=1,
        flags=re.S,
    )
    ARTICLE_JS_PATH.write_text(updated, encoding="utf-8")


def render_vocabulary(article: dict) -> str:
    items = "\n".join(
        f"            <li><strong>{escape(item['term'])}:</strong> {escape(item['meaning'])}</li>"
        for item in article["vocabulary"]
    )
    return f"""    <div class="vocabulary-box">
        <h2>{escape(article["vocabularyTitle"])}</h2>
        <ul>
{items}
        </ul>
    </div>"""


def render_paragraphs(article: dict) -> str:
    blocks = []
    for paragraph in article["paragraphs"]:
        blocks.append(f'    <p class="article-paragraph">{paragraph["html"]}</p>')
        if paragraph.get("translation"):
            blocks.append(f'    <div class="sentence-translation">{escape(paragraph["translation"])}</div>')
    return "\n".join(blocks)


def render_article(article: dict, template: str, asset_version: str) -> str:
    replacements = {
        "{{PAGE_TITLE}}": escape(article["title"]),
        "{{DOWNLOAD_FILE_NAME}}": escape(article["downloadFileName"]),
        "{{ARTICLE_JS_VERSION}}": escape(asset_version),
        "{{DATE}}": escape(article["date"]),
        "{{HEADLINE_WITH_RUBY}}": article["headlineHtml"],
        "{{SOURCE_NOTE}}": escape(article["sourceNote"]),
        '    <p class="article-paragraph">{{PARAGRAPH_1_WITH_RUBY}}</p>\n'
        '    <p class="article-paragraph">{{PARAGRAPH_2_WITH_RUBY}}</p>\n'
        '    <p class="article-paragraph">{{PARAGRAPH_3_WITH_RUBY}}</p>\n'
        '    <p class="article-paragraph">{{PARAGRAPH_4_WITH_RUBY}}</p>': render_paragraphs(article),
        '    <div class="vocabulary-box">\n'
        '        <h2>{{VOCABULARY_TITLE}}</h2>\n'
        '        <ul>\n'
        '            <li><strong>{{WORD_1}}:</strong> {{MEANING_1}}</li>\n'
        '            <li><strong>{{WORD_2}}:</strong> {{MEANING_2}}</li>\n'
        '            <li><strong>{{WORD_3}}:</strong> {{MEANING_3}}</li>\n'
        '            <li><strong>{{WORD_4}}:</strong> {{MEANING_4}}</li>\n'
        '            <li><strong>{{WORD_5}}:</strong> {{MEANING_5}}</li>\n'
        '            <li><strong>{{WORD_6}}:</strong> {{MEANING_6}}</li>\n'
        '            <li><strong>{{WORD_7}}:</strong> {{MEANING_7}}</li>\n'
        '        </ul>\n'
        '    </div>': render_vocabulary(article),
    }
    rendered = template
    for old, new in replacements.items():
        rendered = rendered.replace(old, new)
    return rendered


def write_articles(articles: list[dict]) -> None:
    template = ARTICLE_TEMPLATE_PATH.read_text(encoding="utf-8")
    asset_version = article_navigation_version(articles)
    for article in articles:
        (ROOT / article["file"]).write_text(render_article(article, template, asset_version), encoding="utf-8")


def group_articles(articles: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: list[tuple[str, list[dict]]] = []
    for article in articles:
        if not groups or groups[-1][0] != article["month"]:
            groups.append((article["month"], [article]))
        else:
            groups[-1][1].append(article)
    return groups


def render_index_nav(groups: list[tuple[str, list[dict]]]) -> str:
    return "\n".join(
        f"""                <div class="nav-group">
                    <h3 class="nav-heading">{escape(month)}</h3>
                    <ul class="nav-list">
{chr(10).join(f'                        <li><a class="nav-link" href="#{escape(article_slug(article))}">{escape(article["navLabel"])}</a></li>' for article in month_articles)}
                    </ul>
                </div>"""
        for month, month_articles in groups
    )


def render_index_sections(groups: list[tuple[str, list[dict]]]) -> str:
    sections = []
    for month, month_articles in groups:
        first_date = month_articles[-1]["date"]
        last_date = month_articles[0]["date"]
        range_text = first_date if first_date == last_date else f"{first_date} - {last_date}"
        heading_id = f"{month.lower().replace(' ', '-')}-heading"
        cards = "\n".join(render_index_card(article) for article in month_articles)
        sections.append(
            f"""            <section class="month-section" id="{month.lower().replace(" ", "-")}" aria-labelledby="{heading_id}">
                <div class="section-header">
                    <h2 id="{heading_id}">{escape(month)}</h2>
                    <span class="section-range">{range_text}</span>
                </div>
                <ol class="post-list">
{cards}
                </ol>
            </section>"""
        )
    return "\n".join(sections)


def render_index_card(article: dict) -> str:
    level = f'<span class="level">{escape(article["level"])}</span>' if article.get("level") else ""
    return f"""                    <li class="post-card" id="{escape(article_slug(article))}">
                        <a class="post-link" href="{article_href(article)}">
                            <div class="post-date">{escape(article["date"])}<span>{escape(article_weekday(article))}</span></div>
                            <div>
                                <h3 class="post-title">{escape(article["title"])}</h3>
                                <div class="post-meta">{level}<span class="filename">{escape(article["file"])}</span></div>
                            </div>
                        </a>
                    </li>"""


def write_index(articles: list[dict]) -> None:
    index = INDEX_PATH.read_text(encoding="utf-8")
    groups = group_articles(articles)
    nav_html = render_index_nav(groups)
    index = re.sub(
        r'(<nav class="desktop-nav">).*?(</nav>)',
        rf"\1\n{nav_html}\n        \2",
        index,
        count=1,
        flags=re.S,
    )
    index = re.sub(
        r'(<nav class="mobile-nav-content" aria-label="Folded article navigation">).*?(</nav>)',
        rf"\1\n{nav_html}\n            \2",
        index,
        count=1,
        flags=re.S,
    )
    index = re.sub(
        r'\s*<section class="month-section".*?</section>\s*(?=</main>)',
        f"\n{render_index_sections(groups)}\n",
        index,
        count=1,
        flags=re.S,
    )
    index = re.sub(
        r'<(?P<tag>span|div) class="article-count">.*?</(?P=tag)>',
        lambda match: f'<{match.group("tag")} class="article-count">{len(articles)} articles</{match.group("tag")}>',
        index,
        count=1,
    )
    INDEX_PATH.write_text(index, encoding="utf-8")


def main() -> None:
    articles = load_articles()
    write_articles(articles)
    replace_article_navigation(articles)
    write_index(articles)


if __name__ == "__main__":
    main()
