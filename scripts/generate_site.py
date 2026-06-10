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
ARTICLE_CSS_PATH = ROOT / "assets" / "article.css"
ARTICLE_NAVIGATION_PATH = ROOT / "data" / "article-navigation.json"
FAVICON_PATH = ROOT / "favicon.svg"
INDEX_PATH = ROOT / "index.html"
VOCABULARY_PATH = ROOT / "data" / "vocabulary" / "core-n5-n3.json"
FLASHCARDS_PATH = ROOT / "data" / "flashcards.json"
FLASHCARDS_HTML_PATH = ROOT / "flashcards.html"
FLASHCARDS_JS_PATH = ROOT / "assets" / "flashcards.js"
FLASHCARDS_CSS_PATH = ROOT / "assets" / "flashcards.css"
FLASHCARD_LEVELS = {"N5", "N4", "N3"}
VERB_FORM_SPECS = (
    ("dictionary", "Dictionary", "Dictionary form"),
    ("polite", "Polite", "Polite form"),
    ("past", "Past", "Plain past form"),
    ("negative", "Negative", "Plain negative form"),
    ("te", "Te-form", "Te-form"),
    ("potential", "Potential", "Potential form"),
)
GODAN_A_ROW = {
    "う": "わ",
    "く": "か",
    "ぐ": "が",
    "す": "さ",
    "つ": "た",
    "ぬ": "な",
    "ぶ": "ば",
    "む": "ま",
    "る": "ら",
}
GODAN_I_ROW = {
    "う": "い",
    "く": "き",
    "ぐ": "ぎ",
    "す": "し",
    "つ": "ち",
    "ぬ": "に",
    "ぶ": "び",
    "む": "み",
    "る": "り",
}
GODAN_E_ROW = {
    "う": "え",
    "く": "け",
    "ぐ": "げ",
    "す": "せ",
    "つ": "て",
    "ぬ": "ね",
    "ぶ": "べ",
    "む": "め",
    "る": "れ",
}
GODAN_TE_ENDINGS = {
    "う": "って",
    "つ": "って",
    "る": "って",
    "む": "んで",
    "ぶ": "んで",
    "ぬ": "んで",
    "く": "いて",
    "ぐ": "いで",
    "す": "して",
}
GODAN_PAST_ENDINGS = {
    "う": "った",
    "つ": "った",
    "る": "った",
    "む": "んだ",
    "ぶ": "んだ",
    "ぬ": "んだ",
    "く": "いた",
    "ぐ": "いだ",
    "す": "した",
}


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


def file_version(path: Path) -> str:
    return sha1(path.read_bytes()).hexdigest()[:12]


def split_vocab_term(term: str) -> tuple[str, str]:
    match = re.fullmatch(r"(.+?)（(.+?)）(.*)", term.strip())
    if not match:
        return term.strip(), ""
    suffix = match.group(3).strip()
    return f"{match.group(1).strip()}{suffix}", f"{match.group(2).strip()}{suffix}"


KANA_HIRAGANA_OFFSET = ord("ぁ") - ord("ァ")


def katakana_to_hiragana(text: str) -> str:
    converted = []
    for character in text:
        code = ord(character)
        if 0x30A1 <= code <= 0x30F6:
            converted.append(chr(code + KANA_HIRAGANA_OFFSET))
        else:
            converted.append(character)
    return "".join(converted)


ROMAJI_TO_HIRAGANA = {
    "a": "あ",
    "i": "い",
    "u": "う",
    "e": "え",
    "o": "お",
    "ka": "か",
    "ki": "き",
    "ku": "く",
    "ke": "け",
    "ko": "こ",
    "sa": "さ",
    "shi": "し",
    "su": "す",
    "se": "せ",
    "so": "そ",
    "ta": "た",
    "chi": "ち",
    "tsu": "つ",
    "te": "て",
    "to": "と",
    "na": "な",
    "ni": "に",
    "nu": "ぬ",
    "ne": "ね",
    "no": "の",
    "ha": "は",
    "hi": "ひ",
    "fu": "ふ",
    "he": "へ",
    "ho": "ほ",
    "ma": "ま",
    "mi": "み",
    "mu": "む",
    "me": "め",
    "mo": "も",
    "ya": "や",
    "yu": "ゆ",
    "yo": "よ",
    "ra": "ら",
    "ri": "り",
    "ru": "る",
    "re": "れ",
    "ro": "ろ",
    "wa": "わ",
    "wo": "を",
    "n": "ん",
    "ga": "が",
    "gi": "ぎ",
    "gu": "ぐ",
    "ge": "げ",
    "go": "ご",
    "za": "ざ",
    "ji": "じ",
    "zu": "ず",
    "ze": "ぜ",
    "zo": "ぞ",
    "da": "だ",
    "de": "で",
    "do": "ど",
    "ba": "ば",
    "bi": "び",
    "bu": "ぶ",
    "be": "べ",
    "bo": "ぼ",
    "pa": "ぱ",
    "pi": "ぴ",
    "pu": "ぷ",
    "pe": "ぺ",
    "po": "ぽ",
    "kya": "きゃ",
    "kyu": "きゅ",
    "kyo": "きょ",
    "gya": "ぎゃ",
    "gyu": "ぎゅ",
    "gyo": "ぎょ",
    "sha": "しゃ",
    "shu": "しゅ",
    "sho": "しょ",
    "ja": "じゃ",
    "ju": "じゅ",
    "jo": "じょ",
    "jya": "じゃ",
    "jyu": "じゅ",
    "jyo": "じょ",
    "cha": "ちゃ",
    "chu": "ちゅ",
    "cho": "ちょ",
    "nya": "にゃ",
    "nyu": "にゅ",
    "nyo": "にょ",
    "hya": "ひゃ",
    "hyu": "ひゅ",
    "hyo": "ひょ",
    "bya": "びゃ",
    "byu": "びゅ",
    "byo": "びょ",
    "pya": "ぴゃ",
    "pyu": "ぴゅ",
    "pyo": "ぴょ",
    "mya": "みゃ",
    "myu": "みゅ",
    "myo": "みょ",
    "rya": "りゃ",
    "ryu": "りゅ",
    "ryo": "りょ",
    "fa": "ふぁ",
    "fi": "ふぃ",
    "fe": "ふぇ",
    "fo": "ふぉ",
    "va": "ゔぁ",
    "vi": "ゔぃ",
    "vu": "ゔ",
    "ve": "ゔぇ",
    "vo": "ゔぉ",
    "ti": "てぃ",
    "tu": "とぅ",
    "di": "でぃ",
    "du": "どぅ",
    "che": "ちぇ",
    "she": "しぇ",
    "je": "じぇ",
}


def romaji_to_hiragana(text: str) -> str:
    converted = []
    lower = text.lower()
    index = 0

    while index < len(lower):
        character = lower[index]

        if character in {"/", " ", "-", "·", "・", "(", ")", "[", "]", ",", "."}:
            converted.append(text[index])
            index += 1
            continue

        if not character.isalpha():
            converted.append(text[index])
            index += 1
            continue

        if index + 1 < len(lower) and lower[index] == lower[index + 1] and lower[index] not in {"a", "i", "u", "e", "o", "n"}:
            converted.append("っ")
            index += 1
            continue

        if character == "n":
            next_character = lower[index + 1] if index + 1 < len(lower) else ""
            if next_character in {"", "'", " ", "-", "/", ".", ",", "!", "?", ")", "]"} or next_character not in {"a", "i", "u", "e", "o", "y", "n"}:
                converted.append("ん")
                index += 1
                continue

        matched = False
        for length in (3, 2, 1):
            fragment = lower[index:index + length]
            if fragment in ROMAJI_TO_HIRAGANA:
                converted.append(ROMAJI_TO_HIRAGANA[fragment])
                index += length
                matched = True
                break
        if matched:
            continue

        converted.append(text[index])
        index += 1

    return "".join(converted)


def reading_to_hiragana(reading: str) -> str:
    if not reading:
        return ""
    if re.search(r"[A-Za-z]", reading):
        return romaji_to_hiragana(reading)
    return katakana_to_hiragana(reading)


def stable_vocab_id(*parts: str) -> str:
    key = "\u241f".join(parts)
    return sha1(key.encode("utf-8")).hexdigest()[:14]


def term_surface(term: str) -> str:
    return term.split("/")[0].strip()


def verb_stem(value: str) -> str:
    return value[:-1]


def final_kana(value: str) -> str:
    if not value:
        raise ValueError("Verb term is empty.")
    return value[-1]


def godan_conjugation(value: str, form_id: str) -> str:
    ending = final_kana(value)
    stem = verb_stem(value)
    if ending not in GODAN_I_ROW:
        raise ValueError(f"Unsupported godan ending: {value}")
    if form_id == "dictionary":
        return value
    if form_id == "polite":
        return f"{stem}{GODAN_I_ROW[ending]}ます"
    if form_id == "past":
        if value == "行く":
            return "行った"
        if value == "いく":
            return "いった"
        return f"{stem}{GODAN_PAST_ENDINGS[ending]}"
    if form_id == "negative":
        return f"{stem}{GODAN_A_ROW[ending]}ない"
    if form_id == "te":
        if value == "行く":
            return "行って"
        if value == "いく":
            return "いって"
        return f"{stem}{GODAN_TE_ENDINGS[ending]}"
    if form_id == "potential":
        return f"{stem}{GODAN_E_ROW[ending]}る"
    raise ValueError(f"Unsupported verb form: {form_id}")


def ichidan_conjugation(value: str, form_id: str) -> str:
    stem = verb_stem(value)
    forms = {
        "dictionary": value,
        "polite": f"{stem}ます",
        "past": f"{stem}た",
        "negative": f"{stem}ない",
        "te": f"{stem}て",
        "potential": f"{stem}られる",
    }
    return forms[form_id]


def suru_conjugation(value: str, form_id: str) -> str:
    stem = value[:-2]
    if form_id == "potential" and value != "する":
        return ""
    forms = {
        "dictionary": value,
        "polite": f"{stem}します",
        "past": f"{stem}した",
        "negative": f"{stem}しない",
        "te": f"{stem}して",
        "potential": f"{stem}できる",
    }
    return forms[form_id]


def kuru_conjugation(value: str, form_id: str) -> str:
    if value == "くる":
        forms = {
            "dictionary": value,
            "polite": "きます",
            "past": "きた",
            "negative": "こない",
            "te": "きて",
            "potential": "こられる",
        }
        return forms[form_id]

    forms = {
        "dictionary": value,
        "polite": "来ます",
        "past": "来た",
        "negative": "来ない",
        "te": "来て",
        "potential": "来られる",
    }
    return forms[form_id]


def conjugate_verb(value: str, verb_class: str, form_id: str) -> str:
    if verb_class == "godan":
        return godan_conjugation(value, form_id)
    if verb_class == "ichidan":
        return ichidan_conjugation(value, form_id)
    if verb_class == "suru":
        return suru_conjugation(value, form_id)
    if verb_class == "kuru":
        return kuru_conjugation(value, form_id)
    raise ValueError(f"Unsupported verb class: {verb_class}")


def verb_form_items(item: dict, base_item: dict) -> list[dict]:
    if item.get("partOfSpeech") != "verb":
        return []

    verb_class = item.get("verbClass")
    if verb_class not in {"godan", "ichidan", "suru", "kuru"}:
        raise ValueError(f"Missing or unsupported verbClass for {item['term']}: {verb_class}")

    base_term = term_surface(base_item["term"])
    base_reading = term_surface(base_item.get("readingHiragana") or base_item.get("reading") or "")
    forms = []
    for form_id, form_label, form_description in VERB_FORM_SPECS:
        if form_id == "dictionary":
            continue
        form_term = conjugate_verb(base_term, verb_class, form_id)
        if not form_term:
            continue
        form_reading = conjugate_verb(base_reading, verb_class, form_id) if base_reading else ""
        forms.append(
            {
                **base_item,
                "id": f"{base_item['id']}-verb-{form_id}",
                "term": form_term,
                "reading": "",
                "readingHiragana": form_reading,
                "meaning": f"{form_description} of {base_term}: {base_item['meaning']}",
                "cardKind": "verb-form",
                "baseTerm": base_term,
                "baseReading": base_reading,
                "baseMeaning": base_item["meaning"],
                "verbClass": verb_class,
                "verbForm": form_id,
                "verbFormLabel": form_label,
            }
        )
    return forms


def article_flashcard_items(articles: list[dict]) -> list[dict]:
    items = []
    for article in articles:
        level = article.get("level", "").upper()
        if level not in FLASHCARD_LEVELS:
            continue

        for index, item in enumerate(article.get("vocabulary", []), start=1):
            term, reading = split_vocab_term(item["term"])
            item_id = f"article-{stable_vocab_id(article['id'], str(index), term, item['meaning'])}"
            base_item = {
                "id": item_id,
                "level": level,
                "term": term,
                "reading": reading,
                "readingHiragana": reading_to_hiragana(reading),
                "meaning": item["meaning"],
                "source": "article",
                "sourceId": article["id"],
                "sourceTitle": article["title"],
                "sourceLabel": article["navLabel"],
                "sourceHref": article_href(article),
                "tags": ["article-vocab", article["id"]],
            }
            if item.get("partOfSpeech"):
                base_item["partOfSpeech"] = item["partOfSpeech"]
            if item.get("verbClass"):
                base_item["verbClass"] = item["verbClass"]
            items.append(base_item)
            items.extend(verb_form_items(item, base_item))
    return items


def load_core_vocabulary() -> list[dict]:
    if not VOCABULARY_PATH.exists():
        return []

    data = json.loads(VOCABULARY_PATH.read_text(encoding="utf-8"))
    items = []
    for deck in data.get("decks", []):
        deck_id = deck["id"]
        deck_level = deck.get("level", "").upper()
        for item in deck.get("items", []):
            level = item.get("level", deck_level).upper()
            if level not in FLASHCARD_LEVELS:
                continue

            item_id = f"core-{stable_vocab_id(deck_id, item['id'], item['term'], item['meaning'])}"
            base_item = {
                "id": item_id,
                "level": level,
                "term": item["term"],
                "reading": item.get("reading", ""),
                "readingHiragana": reading_to_hiragana(item.get("reading", "")),
                "meaning": item["meaning"],
                "source": "core",
                "sourceId": deck_id,
                "sourceTitle": deck.get("title", deck_id),
                "sourceLabel": deck.get("title", deck_id),
                "sourceHref": deck.get("sourceUrl", ""),
                "tags": item.get("tags", []),
            }
            if item.get("partOfSpeech"):
                base_item["partOfSpeech"] = item["partOfSpeech"]
            if item.get("verbClass"):
                base_item["verbClass"] = item["verbClass"]
            items.append(base_item)
            items.extend(verb_form_items(item, base_item))
    return items


def write_flashcards_manifest(articles: list[dict]) -> None:
    core_items = load_core_vocabulary()
    article_items = article_flashcard_items(articles)
    items = core_items + article_items
    level_counts = {level: 0 for level in sorted(FLASHCARD_LEVELS)}
    for item in items:
        level_counts[item["level"]] += 1

    payload = {
        "generatedFrom": {
            "coreVocabulary": str(VOCABULARY_PATH.relative_to(ROOT)),
            "articleManifest": str(ARTICLES_PATH.relative_to(ROOT)),
        },
        "levels": level_counts,
        "items": items,
    }
    FLASHCARDS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_article_navigation_manifest(articles: list[dict]) -> None:
    ARTICLE_NAVIGATION_PATH.write_text(
        json.dumps(article_navigation(articles), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
        "{{ARTICLE_ID}}": escape(article["id"]),
        "{{DOWNLOAD_FILE_NAME}}": escape(article["downloadFileName"]),
        "{{ARTICLE_JS_VERSION}}": escape(asset_version),
        "{{ARTICLE_CSS_VERSION}}": escape(file_version(ARTICLE_CSS_PATH)),
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
    asset_version = file_version(ARTICLE_JS_PATH)
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
{chr(10).join(f'                        <li><a class="nav-link" href="{article_href(article)}">{escape(article["navLabel"])}</a></li>' for article in month_articles)}
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
    favicon_link = '<link rel="icon" type="image/svg+xml" href="./favicon.svg">'
    if favicon_link not in index:
        index = re.sub(
            r'(<title>[^<]*</title>)',
            rf"\1\n    {favicon_link}",
            index,
            count=1,
        )
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


def write_flashcards_page() -> None:
    html = FLASHCARDS_HTML_PATH.read_text(encoding="utf-8")
    favicon_link = '<link rel="icon" type="image/svg+xml" href="./favicon.svg">'
    if favicon_link not in html:
        html = re.sub(
            r'(<title>[^<]*</title>)',
            rf"\1\n    {favicon_link}",
            html,
            count=1,
        )
    html = re.sub(
        r'./assets/flashcards\.css(?:\?v=[^"]*)?',
        f'./assets/flashcards.css?v={file_version(FLASHCARDS_CSS_PATH)}',
        html,
        count=1,
    )
    html = re.sub(
        r'./assets/flashcards\.js(?:\?v=[^"]*)?',
        f'./assets/flashcards.js?v={file_version(FLASHCARDS_JS_PATH)}',
        html,
        count=1,
    )
    FLASHCARDS_HTML_PATH.write_text(html, encoding="utf-8")


def main() -> None:
    articles = load_articles()
    write_article_navigation_manifest(articles)
    write_articles(articles)
    write_index(articles)
    write_flashcards_manifest(articles)
    write_flashcards_page()


if __name__ == "__main__":
    main()
