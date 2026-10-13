"""Detecting the language of a text by its function words.

Used to drop generated items written in a language other than their
document's. The question asked is not "what language is this at all" but
"which of the languages we know does the text look like", and the share of
frequent function words answers it without a model or a separate library.
"""

from __future__ import annotations

import re

from syft_benchmark.generation.abstractive import TIERS, TTIL_HEAD
from syft_benchmark.generation.extractive import FILL_IN_PREFIX
from syft_benchmark.generation.negative import NOT_IN_CORPUS
from syft_benchmark.generation.pair import Pair

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# The fixed English wording the cleaners put around what the writer wrote.
_SCAFFOLDING: tuple[str, ...] = (
    TTIL_HEAD,
    *(tier["instruction"] for tier in TIERS.values()),
    "Topic:",
    FILL_IN_PREFIX,
    NOT_IN_CORPUS,
)
# An option letter opening a line: "A) ...".
_OPTION_LETTER_RE = re.compile(r"^\s*[A-D]\)\s*", re.MULTILINE)

# The share of function words below which we take the language to be a
# different one. The threshold is low: technical documentation has noticeably
# fewer function words than prose.
_HIT_THRESHOLD = 0.08

# How many words are enough to judge the language by.
_MIN_WORDS = 12

# The most frequent function words of each language, lowercase. Elided forms
# ("l'", "d'", "dell'") are split off by ``_WORD_RE`` and appear as one-letter
# or short words.
_FUNCTION_WORDS: dict[str, str] = {
    "en": """
        the of and to a in is it that for was on are as with be by at this have
        from or an not but his they he she her we you i which their has had were
        been its there can will would all one if so what when who more no about
        out up than them into some could other these then our also only how
        after any most us may do does did over such between should through those
        each both very where while because before under again my him me your
        just being here why own
    """,
    "ru": """
        и в во не что он на я с со как а то все всё она так его но да ты к у же
        вы за бы по только ее её мне было вот от меня еще ещё нет о об из ему
        теперь когда даже ли если уже или ни быть был него до вас вам ведь там
        потом себя ничего ей может они тут где есть надо ней для мы тебя их чем
        была сам чтобы без чего раз тоже себе под будет тогда кто этот этого это
        эти этой того при были также который которые которая которых после
        между более свой своей том
    """,
    "de": """
        der die das und in zu den von mit sich des auf für ist im dem nicht ein
        eine als auch es an er hat aus bei sie nach wird einer um am sind noch
        wie einem über einen so zum war haben nur oder aber vor zur bis mehr
        durch man dass sein wurde sei kann ich wir ihr werden diese dieser
        dieses wenn schon seine ihre unter gegen sehr hier alle wieder was
        zwischen ohne weil denn also doch wo nun
    """,
    "fr": """
        le la les de des du un une et en à au aux est que qui dans pour pas sur
        ne se ce cette ces il elle ils elles nous vous je on avec par plus son
        sa ses leur leurs mais ou comme été être sont ont a y tout tous aussi
        bien sans entre après avant sous très même lui dont où si peut fait
        avait était encore notre votre qu d l n s c j
    """,
    "es": """
        de la que el en y a los del se las por un para con no una su al lo como
        más pero sus le ya o este sí porque esta entre cuando muy sin sobre
        también me hasta hay donde quien desde todo nos durante todos uno les ni
        contra otros ese eso ante ellos e esto mí antes algunos qué unos yo otro
        otras otra él tanto esa estos mucho cual poco ella es son fue ser ha han
        era está están había sido puede tiene cada según
    """,
    "it": """
        di e il la che in a per un è del non una con i si da le al della dei
        sono lo gli come ma più anche nel alla delle ha se o questo questa ci
        nella era suo sua loro tra fra ad degli dal ed essere stato hanno dopo
        quando cui sul sulla molto tutti tutto ancora già dove perché così
        quindi mentre solo ne l d all dell nell sull questi quella quello aveva
        fu può ogni sempre senza prima poi noi voi lui lei io
    """,
    "pt": """
        de a o que e do da em um para é com não uma os no se na por mais as dos
        como mas foi ao ele das tem à seu sua ou ser quando muito há nos já está
        eu também só pelo pela até isso ela entre era depois sem mesmo aos ter
        seus quem nas me esse eles estão você tinha foram essa num nem suas meu
        às minha têm numa pelos elas havia seja qual será nós são sobre este
        esta isto ainda pode onde porque então assim
    """,
    "nl": """
        de en van het een in is dat op te zijn met voor niet aan er die ook als
        bij door of om wordt maar worden hij ze zij naar uit nog tot dan over
        wel kan was werd al hun heeft hebben deze dit we wij je ik meer geen na
        zo onder wat waar omdat tussen tegen zou moet alleen haar hem ons mijn
        men toen nu veel zich want zonder sinds hoe wie
    """,
}

STOP_WORDS: dict[str, frozenset[str]] = {
    lang: frozenset(words.split()) for lang, words in _FUNCTION_WORDS.items()
}

# The languages told apart, in the order of preference on a tie.
LANGUAGES: tuple[str, ...] = tuple(STOP_WORDS)


def detect_language(text: str, candidates: tuple[str, ...] = LANGUAGES) -> str | None:
    """Which of the candidate languages the text most resembles.

    Args:
        text: A chunk of the document, or an item's text
        candidates: The codes of the languages to tell apart; codes without
            a word list are skipped

    Returns:
        A language code, or None if none of them reached the threshold
    """
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if len(words) < _MIN_WORDS:
        return None

    best: tuple[float, str] | None = None
    for lang in candidates:
        stop = STOP_WORDS.get(lang)
        if not stop:
            continue
        share = sum(1 for w in words if w in stop) / len(words)
        if share >= _HIT_THRESHOLD and (best is None or share > best[0]):
            best = (share, lang)

    return best[1] if best else None


def written_text(pair: Pair) -> str:
    """An item's text as its writer wrote it, for telling its language.

    The fixed English wording around it (an instruction, "Fill in the blank:",
    option letters) is left out: counted in, it tips a short item in another
    language towards English.
    """
    text = "\n".join([pair.question, pair.answer, *pair.distractors])
    for fixed in _SCAFFOLDING:
        text = text.replace(fixed, " ")
    return _OPTION_LETTER_RE.sub(" ", text)
