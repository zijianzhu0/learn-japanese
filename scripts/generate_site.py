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
IG_VIDEOS_HTML_PATH = ROOT / "ig-videos.html"
IG_VIDEOS_JS_PATH = ROOT / "assets" / "ig-videos.js"
IG_VIDEOS_CSS_PATH = ROOT / "assets" / "ig-videos.css"
FLASHCARD_LEVELS = {"N5", "N4", "N3"}
VERB_FORM_SPECS = (
    ("dictionary", "Dictionary", "Dictionary form"),
    ("polite", "Polite", "Polite form"),
    ("past", "Past", "Plain past form"),
    ("negative", "Negative", "Plain negative form"),
    ("te", "Te-form", "Te-form"),
    ("potential", "Potential", "Potential form"),
)
EXAMPLE_SENTENCE_COUNT = 5
DEFAULT_COMBO_WORDS = ("朝", "学校", "友だち", "駅", "家")
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


def combo_words_for_items(items: list[dict], current_index: int) -> list[str]:
    words = []
    for offset in range(1, len(items) + 1):
        for candidate_index in (current_index + offset, current_index - offset):
            if 0 <= candidate_index < len(items):
                candidate = items[candidate_index]
                word = term_surface(str(candidate.get("term", "")))
                if candidate.get("partOfSpeech") == "verb" or word.endswith("い"):
                    continue
                if word and word not in words:
                    words.append(word)
            if len(words) >= EXAMPLE_SENTENCE_COUNT:
                return words
    return words


def padded_combo_words(combo_words: list[str] | None) -> list[str]:
    words = []
    for word in list(combo_words or []) + list(DEFAULT_COMBO_WORDS):
        if word and word not in words:
            words.append(word)
        if len(words) == EXAMPLE_SENTENCE_COUNT:
            return words
    return words


def english_gloss(item: dict, term: str) -> str:
    meaning = str(item.get("baseMeaning") or item.get("meaning") or term)
    gloss = meaning.split(";")[0].split(",")[0].split(":")[0].split("/")[0].strip()
    if len(gloss) > 1 and gloss[0].isupper() and gloss[1].islower():
        return f"{gloss[0].lower()}{gloss[1:]}"
    return gloss


def english_verb_action(item: dict, term: str) -> str:
    gloss = english_gloss(item, term)
    return gloss[3:] if gloss.lower().startswith("to ") else gloss


def selected_example_templates(term: str, category: str, templates: list[tuple[str, str]]) -> list[tuple[str, str]]:
    if len(templates) < EXAMPLE_SENTENCE_COUNT:
        raise ValueError(f"Need at least {EXAMPLE_SENTENCE_COUNT} templates for {category}.")

    ranked = sorted(
        templates,
        key=lambda template: sha1(f"{category}:{term}:{template[0]}".encode("utf-8")).hexdigest(),
    )
    return ranked[:EXAMPLE_SENTENCE_COUNT]


def render_example_templates(
    term: str,
    category: str,
    templates: list[tuple[str, str]],
    context: dict[str, str],
) -> list[dict]:
    context = {"term": term, **context}
    return [
        {"ja": ja.format(**context), "en": en.format(**context)}
        for ja, en in selected_example_templates(term, category, templates)
    ]


VERB_EXAMPLE_TEMPLATES = {
    "dictionary": [
        ("明日は早く起きて{term}つもりです。", "Tomorrow I plan to get up early and {action}."),
        ("一人で{term}ことがあります。", "Sometimes I {action} by myself."),
        ("家に帰ってから{term}予定です。", "I plan to {action} after I get home."),
        ("疲れていても、今日は少しだけ{term}ようにします。", "Even if I am tired, I will try to {action} a little today."),
        ("予定について話したあとで{term}ことにしました。", "After talking about plans, I decided to {action}."),
        ("朝のうちに{term}ようにしています。", "I try to {action} during the morning."),
        ("先生に言われる前に{term}ようにしています。", "I try to {action} before the teacher tells me."),
        ("週末だけはゆっくり{term}時間があります。", "Only on weekends do I have time to {action}."),
        ("出かける前に{term}必要があります。", "I need to {action} before going out."),
        ("友だちを待つ間に{term}ことにしました。", "I decided to {action} while waiting for my friend."),
        ("忘れないように、先に{term}つもりです。", "So I do not forget, I plan to {action} first."),
        ("できれば今日中に{term}つもりです。", "If possible, I plan to {action} sometime today."),
        ("急がずに{term}ほうがいいです。", "It is better to {action} without rushing."),
    ],
    "polite": [
        ("毎朝、いつもより早く{term}。", "Every morning, I {action} earlier than usual."),
        ("家に帰ってから、すぐ{term}。", "After I get home, I {action} right away."),
        ("予定の話をしたあとで{term}。", "After talking about plans, I {action}."),
        ("今日は少しだけ{term}。", "Today, I {action} just a little."),
        ("寝る前に、ゆっくり{term}。", "Before bed, I {action} slowly."),
        ("先生の前では、できるだけ丁寧に{term}。", "In front of the teacher, I {action} as politely as I can."),
        ("駅に着いたら、まず{term}。", "When I arrive at the station, I {action} first."),
        ("用事が終わったら{term}。", "After my errand is finished, I {action}."),
        ("友だちが来る前に{term}。", "Before my friend comes, I {action}."),
        ("今日は早めに準備して{term}。", "Today I get ready early and {action}."),
        ("みんなの前では静かに{term}。", "In front of everyone, I {action} quietly."),
        ("時間があれば、もう一度{term}。", "If there is time, I {action} one more time."),
    ],
    "past": [
        ("昨日は疲れていたけれど、ちゃんと{term}。", "Yesterday I was tired, but I still {action} properly."),
        ("友だちと話したあとで{term}。", "After talking with a friend, I {action}."),
        ("予定を確認してから{term}。", "After checking my plans, I {action}."),
        ("急いでいたので、早めに{term}。", "Because I was in a hurry, I {action} early."),
        ("夜、家に帰ってから{term}。", "At night, I got home and then {action}."),
        ("先生に聞く前に、自分で{term}。", "Before asking the teacher, I {action} by myself."),
        ("休憩のあとで少しだけ{term}。", "After a break, I {action} just a little."),
        ("電車を待っている間に{term}。", "While waiting for the train, I {action}."),
        ("思ったより早く{term}。", "I {action} earlier than I expected."),
        ("友だちに頼まれて{term}。", "A friend asked me, so I {action}."),
        ("朝ごはんの前に{term}。", "Before breakfast, I {action}."),
        ("次の予定を考えながら{term}。", "While thinking about the next plan, I {action}."),
    ],
    "negative": [
        ("今日は時間がないので{term}。", "I do not {action} today because I have no time."),
        ("疲れている時は、無理に{term}。", "When I am tired, I do not force myself to {action}."),
        ("準備が終わるまで{term}。", "I do not {action} until preparation is finished."),
        ("雨の日は、あまり{term}。", "On rainy days, I do not {action} much."),
        ("予定が変わった日は、すぐには{term}。", "When my plans change, I do not {action} right away."),
        ("先生が来るまでは{term}。", "I do not {action} until the teacher comes."),
        ("予定を確認するまでは{term}。", "I do not {action} until I check my plans."),
        ("今日は気分が乗らないので{term}。", "I do not {action} today because I am not in the mood."),
        ("急いでいる時ほど{term}ようにしています。", "The more rushed I am, the more I try not to {action}."),
        ("友だちがいる前では{term}。", "I do not {action} in front of my friend."),
        ("夜遅くには{term}ことにしています。", "I make it a rule not to {action} late at night."),
        ("必要なものが見つかるまで{term}。", "I do not {action} until the thing I need is found."),
    ],
    "te": [
        ("少し休んでから、もう一度{term}ください。", "Please rest a little, then {action} again."),
        ("予定を確認してから{term}ください。", "Please check the plan, then {action}."),
        ("友だちにも聞いて、いっしょに{term}みましょう。", "Ask a friend too, and let's try to {action} together."),
        ("先に準備をしてから{term}ください。", "Please get ready first, then {action}."),
        ("急がないで、ゆっくり{term}ください。", "Please do not hurry; {action} slowly."),
        ("少し待って、そこで{term}ください。", "Please wait a little, and {action} there."),
        ("分からなかったら、もう一度{term}みてください。", "If you do not understand, please try to {action} again."),
        ("先生に見せる前に{term}ください。", "Please {action} before showing it to the teacher."),
        ("音を聞いてから{term}みましょう。", "Listen to the sound, then let's try to {action}."),
        ("今日は短く{term}ください。", "Please {action} briefly today."),
        ("順番を忘れないで{term}ください。", "Please do not forget the order; {action}."),
        ("最後まであきらめないで{term}ください。", "Please do not give up; {action} until the end."),
    ],
    "potential": [
        ("時間があれば、一人でも{term}。", "If there is time, I can {action} even by myself."),
        ("練習すれば、もっと上手に{term}ようになります。", "If I practice, I will be able to {action} better."),
        ("少し休んだあとなら、たぶん{term}。", "After resting a little, I can probably {action}."),
        ("友だちと一緒なら、安心して{term}。", "If I am with a friend, I can {action} without worry."),
        ("予定が終われば、すぐ{term}。", "Once my plans are finished, I can {action} right away."),
        ("この場所なら静かに{term}。", "In this place, I can {action} quietly."),
        ("準備ができれば、もっと楽に{term}。", "If I am prepared, I can {action} more easily."),
        ("先生に教えてもらえば{term}ようになります。", "If the teacher shows me, I will be able to {action}."),
        ("今日は元気だから、まだ{term}。", "Because I feel energetic today, I can still {action}."),
        ("道が分かれば、一人でも{term}。", "If I know the way, I can {action} alone."),
        ("休憩のあとなら落ち着いて{term}。", "After a break, I can {action} calmly."),
        ("もう少し時間があれば最後まで{term}。", "With a little more time, I can {action} to the end."),
    ],
}


ADJECTIVE_EXAMPLE_TEMPLATES = {
    "danger": [
        ("この道は少し{term}です。", "This road is a little {gloss}."),
        ("その場所は夜になると{term}です。", "That place becomes {gloss} at night."),
        ("一人で行くのは{term}です。", "Going alone is {gloss}."),
        ("この計画は思ったより{term}です。", "This plan is more {gloss} than I expected."),
        ("川の近くで遊ぶのは{term}です。", "Playing near the river is {gloss}."),
        ("雨の日の駅前は少し{term}です。", "The area in front of the station is a little {gloss} on rainy days."),
        ("急いで渡ると{term}です。", "Crossing in a hurry is {gloss}."),
        ("先生はその道が{term}だと言いました。", "The teacher said that road is {gloss}."),
        ("子どもだけで使うには{term}です。", "It is {gloss} for children to use alone."),
        ("暗くなる前に帰らないと{term}です。", "It is {gloss} if we do not go home before it gets dark."),
    ],
    "bright": [
        ("朝の部屋はとても{term}です。", "The room in the morning is very {gloss}."),
        ("今日の空は思ったより{term}です。", "Today's sky is brighter than I expected."),
        ("友だちは{term}服を選びました。", "My friend chose {gloss} clothes."),
        ("駅の前の道は夜でも{term}です。", "The road in front of the station is {gloss} even at night."),
        ("妹の表情はいつも{term}です。", "My younger sister's expression is always {gloss}."),
        ("新しい教室は前より{term}です。", "The new classroom is more {gloss} than before."),
        ("この写真は色が{term}です。", "The colors in this photo are {gloss}."),
        ("窓を開けると部屋が{term}なりました。", "When I opened the window, the room became {gloss}."),
        ("店の看板がとても{term}です。", "The shop sign is very {gloss}."),
        ("朝の声が{term}感じでした。", "The morning voice had a {gloss} feeling."),
    ],
    "cold": [
        ("朝の水はとても{term}です。", "The morning water is very {gloss}."),
        ("この部屋は思ったより{term}です。", "This room is more {gloss} than I expected."),
        ("今日は風が{term}です。", "The wind is {gloss} today."),
        ("外に出ると、手が{term}です。", "When I go outside, my hands are {gloss}."),
        ("冷蔵庫の中の飲み物はまだ{term}です。", "The drink in the fridge is still {gloss}."),
        ("駅で待っている間、足が{term}なりました。", "While waiting at the station, my feet became {gloss}."),
        ("雨のあとで空気が{term}です。", "After the rain, the air is {gloss}."),
        ("このお茶はもう{term}です。", "This tea is already {gloss}."),
        ("夜の廊下は少し{term}です。", "The hallway at night is a little {gloss}."),
        ("山の上は夏でも{term}です。", "On top of the mountain, it is {gloss} even in summer."),
    ],
    "hot": [
        ("このスープはとても{term}です。", "This soup is very {gloss}."),
        ("今日は外が思ったより{term}です。", "Outside is more {gloss} than I expected today."),
        ("部屋の中はまだ{term}です。", "The room is still {gloss}."),
        ("駅まで歩くと体が{term}です。", "When I walk to the station, my body feels {gloss}."),
        ("このお茶は少し{term}です。", "This tea is a little {gloss}."),
        ("昼の電車はとても{term}です。", "The train at noon is very {gloss}."),
        ("窓を閉めるとすぐ{term}なります。", "When I close the window, it quickly becomes {gloss}."),
        ("今日は風がなくて{term}です。", "There is no wind today, so it is {gloss}."),
        ("鍋のふたを開けたら{term}空気が出ました。", "{gloss} air came out when I opened the pot lid."),
        ("走ったあとで顔が{term}です。", "After running, my face feels {gloss}."),
    ],
    "general": [
        ("この場所は少し{term}です。", "This place is a little {gloss}."),
        ("今日の天気は思ったより{term}です。", "Today's weather is more {gloss} than I expected."),
        ("友だちは{term}物を選びました。", "My friend chose something {gloss}."),
        ("この話はとても{term}です。", "This story is very {gloss}."),
        ("朝の町はまだ{term}です。", "The town in the morning is still {gloss}."),
        ("この店の雰囲気は{term}です。", "The atmosphere of this shop is {gloss}."),
        ("先生の説明は少し{term}感じがしました。", "The teacher's explanation felt a little {gloss}."),
        ("旅行の前日は気持ちが{term}です。", "The day before a trip, my feelings are {gloss}."),
        ("友だちの部屋はいつも{term}です。", "My friend's room is always {gloss}."),
        ("この映画は最後まで{term}です。", "This movie is {gloss} until the end."),
    ],
}


NOUN_EXAMPLE_TEMPLATES = [
    ("ニュースで{term}を見ました。", "I saw {gloss} in the news."),
    ("先生が{term}について説明しました。", "The teacher explained {gloss}."),
    ("学校で{term}と{combo1}をノートに書きました。", "At school, I wrote {gloss} and {combo1} in my notebook."),
    ("友だちは{term}より{combo2}を先に覚えました。", "My friend remembered {combo2} before {gloss}."),
    ("{combo3}の話を聞いて、{term}を思い出しました。", "After hearing about {combo3}, I remembered {gloss}."),
    ("朝の電車で{term}についての記事を読みました。", "On the morning train, I read an article about {gloss}."),
    ("駅の近くで{term}を探しました。", "I looked for {gloss} near the station."),
    ("友だちに{term}の意味を聞かれました。", "A friend asked me the meaning of {gloss}."),
    ("{combo1}と{term}を比べると、違いが分かります。", "When I compare {combo1} and {gloss}, I can see the difference."),
    ("机の上に{term}のメモを置きました。", "I put a note about {gloss} on the desk."),
    ("昨日の会話で{term}が何度も出ました。", "{gloss} came up many times in yesterday's conversation."),
    ("{combo2}を調べていたら、{term}も見つかりました。", "While looking up {combo2}, I also found {gloss}."),
    ("家族に{term}のニュースを話しました。", "I told my family the news about {gloss}."),
    ("この文章では{term}が大事な言葉です。", "In this passage, {gloss} is an important word."),
    ("{term}を聞いて、すぐ{combo3}を連想しました。", "When I heard {gloss}, I immediately associated it with {combo3}."),
]


def fallback_example_sentences(
    item: dict,
    term: str,
    combo_words: list[str] | None = None,
    verb_form: str | None = None,
) -> list[dict]:
    term = term_surface(term)
    combo1, combo2, combo3, combo4, combo5 = padded_combo_words(combo_words)
    part_of_speech = item.get("partOfSpeech")
    gloss = english_gloss(item, term)
    action = english_verb_action(item, term)

    if part_of_speech == "verb" or verb_form:
        form_key = verb_form or "dictionary"
        return render_example_templates(
            term,
            f"verb-{form_key}",
            VERB_EXAMPLE_TEMPLATES[form_key],
            {
                "action": action,
                "combo1": combo1,
                "combo2": combo2,
                "combo3": combo3,
                "combo4": combo4,
                "combo5": combo5,
            },
        )

    if term.endswith("い"):
        lower_gloss = gloss.lower()
        if "dangerous" in lower_gloss or "risky" in lower_gloss:
            adjective_key = "danger"
        elif "bright" in lower_gloss or "colorful" in lower_gloss:
            adjective_key = "bright"
        elif "cold" in lower_gloss or "cool" in lower_gloss:
            adjective_key = "cold"
        elif "hot" in lower_gloss or "warm" in lower_gloss:
            adjective_key = "hot"
        else:
            adjective_key = "general"
        return render_example_templates(
            term,
            f"adjective-{adjective_key}",
            ADJECTIVE_EXAMPLE_TEMPLATES[adjective_key],
            {"gloss": gloss},
        )

    return render_example_templates(
        term,
        "noun",
        NOUN_EXAMPLE_TEMPLATES,
        {
            "gloss": gloss,
            "combo1": combo1,
            "combo2": combo2,
            "combo3": combo3,
            "combo4": combo4,
            "combo5": combo5,
        },
    )


def normalize_example_sentences(
    item: dict,
    term: str,
    combo_words: list[str] | None = None,
    verb_form: str | None = None,
) -> list[dict]:
    examples = item.get("exampleSentences")
    if examples is None:
        return fallback_example_sentences(item, term, combo_words, verb_form)

    if len(examples) != EXAMPLE_SENTENCE_COUNT:
        raise ValueError(
            f"Expected {EXAMPLE_SENTENCE_COUNT} exampleSentences for {term}, got {len(examples)}"
        )

    normalized = []
    for index, example in enumerate(examples, start=1):
        if not isinstance(example, dict):
            raise ValueError(f"Example sentence {index} for {term} must be an object.")
        ja = str(example.get("ja", "")).strip()
        en = str(example.get("en", "")).strip()
        if not ja or not en:
            raise ValueError(f"Example sentence {index} for {term} needs ja and en.")
        normalized.append({"ja": ja, "en": en})
    return normalized


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


def verb_form_items(item: dict, base_item: dict, combo_words: list[str] | None = None) -> list[dict]:
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
                "exampleSentences": normalize_example_sentences(item, form_term, combo_words, form_id),
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

        vocabulary = article.get("vocabulary", [])
        for index, item in enumerate(vocabulary, start=1):
            term, reading = split_vocab_term(item["term"])
            combo_words = combo_words_for_items(vocabulary, index - 1)
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
                "exampleSentences": normalize_example_sentences(item, term, combo_words),
            }
            if item.get("partOfSpeech"):
                base_item["partOfSpeech"] = item["partOfSpeech"]
            if item.get("verbClass"):
                base_item["verbClass"] = item["verbClass"]
            items.append(base_item)
            items.extend(verb_form_items(item, base_item, combo_words))
    return items


def load_core_vocabulary() -> list[dict]:
    if not VOCABULARY_PATH.exists():
        return []

    data = json.loads(VOCABULARY_PATH.read_text(encoding="utf-8"))
    items = []
    for deck in data.get("decks", []):
        deck_id = deck["id"]
        deck_level = deck.get("level", "").upper()
        deck_items = deck.get("items", [])
        for index, item in enumerate(deck_items):
            level = item.get("level", deck_level).upper()
            if level not in FLASHCARD_LEVELS:
                continue

            combo_words = combo_words_for_items(deck_items, index)
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
                "exampleSentences": normalize_example_sentences(item, item["term"], combo_words),
            }
            if item.get("partOfSpeech"):
                base_item["partOfSpeech"] = item["partOfSpeech"]
            if item.get("verbClass"):
                base_item["verbClass"] = item["verbClass"]
            items.append(base_item)
            items.extend(verb_form_items(item, base_item, combo_words))
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


def write_ig_videos_page() -> None:
    html = IG_VIDEOS_HTML_PATH.read_text(encoding="utf-8")
    favicon_link = '<link rel="icon" type="image/svg+xml" href="./favicon.svg">'
    if favicon_link not in html:
        html = re.sub(
            r'(<title>[^<]*</title>)',
            rf"\1\n    {favicon_link}",
            html,
            count=1,
        )
    html = re.sub(
        r'./assets/ig-videos\.css(?:\?v=[^"]*)?',
        f'./assets/ig-videos.css?v={file_version(IG_VIDEOS_CSS_PATH)}',
        html,
        count=1,
    )
    html = re.sub(
        r'./assets/ig-videos\.js(?:\?v=[^"]*)?',
        f'./assets/ig-videos.js?v={file_version(IG_VIDEOS_JS_PATH)}',
        html,
        count=1,
    )
    IG_VIDEOS_HTML_PATH.write_text(html, encoding="utf-8")


def main() -> None:
    articles = load_articles()
    write_article_navigation_manifest(articles)
    write_articles(articles)
    write_index(articles)
    write_flashcards_manifest(articles)
    write_flashcards_page()
    write_ig_videos_page()


if __name__ == "__main__":
    main()
