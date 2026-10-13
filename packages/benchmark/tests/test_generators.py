"""The eight generators: rejection, parsing and the bounds of applicability."""

from __future__ import annotations

import random
import re

import pytest

from syft_benchmark.config import ExpectedBehavior
from syft_benchmark.generation import (
    CONTROL_KEYS,
    GENERATORS,
    reject_reason,
    review_claims,
)
from syft_benchmark.generation.abstractive import (
    clean_multihop,
    clean_tiered,
    clean_ttil,
)
from syft_benchmark.generation.extractive import is_prose, parse_combined
from syft_benchmark.generation.language import detect_language
from syft_benchmark.generation.pair import Pair

DOC = "Space registers with the Hub. The Hub stores endpoint metadata."


# --- the line-up -----------------------------------------------------------


def test_seven_from_livetruth_plus_our_own() -> None:
    """The original's seven generators are in place, the eighth is ours."""
    assert {k for k, g in GENERATORS.items() if not g.is_control} == {
        "named_entity_masking",
        "numeric_masking",
        "temporal_masking",
        "mcq",
        "two_truths_one_lie",
        "multihop_synthesis",
        "tiered_explanation",
        "qa",
    }


def test_the_control_half_exists() -> None:
    """Without control questions the dataset measures half the behaviour.

    Every other generator builds its item FROM a chunk, that is, the question is
    answerable by construction: what the pair does when there is no answer would
    not be measured at all.
    """
    assert set(CONTROL_KEYS) == {"unanswerable_property", "false_premise"}
    assert GENERATORS["unanswerable_property"].expected is ExpectedBehavior.ABSTAIN
    assert (
        GENERATORS["false_premise"].expected is ExpectedBehavior.CORRECT_PREMISE
    ), "a false premise is refuted, not declined"


def test_unanswerable_needs_no_judge() -> None:
    """There is no correct answer: behaviour is measured, and needs no model."""
    assert GENERATORS["unanswerable_property"].grading == "behavior"


def test_document_scope_only_where_a_fragment_is_not_enough() -> None:
    """You cannot connect two facts or lay out a topic from a single paragraph."""
    document_scope = {k for k, g in GENERATORS.items() if g.scope == "document"}
    assert document_scope == {"multihop_synthesis", "tiered_explanation"}


def test_choice_tasks_need_no_judge() -> None:
    for key in ("mcq", "two_truths_one_lie"):
        assert GENERATORS[key].grading == "letter"


# --- rejection by item type ------------------------------------------------


def test_masked_sentence_keeps_a_pronoun_with_its_subject() -> None:
    """A pronoun passes when the sentence names who it is."""
    masked = "Fill in the blank: The Hub restarts when its port ______ is busy."
    assert reject_reason(masked, DOC, task_type="extractive") is None


@pytest.mark.parametrize(
    ("sentence", "reason"),
    [
        # Bloomberg, 10 Oct: who "he" is, the reader never learns.
        (
            "I mean, he’s still worth ______, which is a lot.",
            "a pronoun without an antecedent",
        ),
        (
            "It’s time to break out the world’s smallest violin for ______.",
            "a pronoun without an antecedent",
        ),
        (
            "The engineers said this decision cost them ______ of the budget.",
            "a demonstrative without an antecedent",
        ),
        (
            "“THE ENEMY,” I’ll yell, and earn me a lifetime ban on ______.",
            "a quote",
        ),
        (
            '______ called the release "a turning point for the Hub".',
            "a quote",
        ),
    ],
)
def test_masked_sentence_must_stand_alone(sentence: str, reason: str) -> None:
    question = f"Fill in the blank: {sentence}"
    assert reject_reason(question, DOC, task_type="extractive") == reason


@pytest.mark.parametrize(
    "sentence",
    [
        # Bloomberg, 10 Oct: cut from inside a quote, its opening mark is gone.
        "______ so far has been the best ever… $845 billion.”",
        'The release notes end with ______ and the line "see you soon.',
        "Директор компании добавил: «Мы откроем офис в ______.",
        # Wording, by its length; the blank is one of the words.
        'The Hub docs say "restart the ______ after every config change" twice.',
        "«Мы запустим новую версию в ______ году», — сообщил директор.",
        "„Wir starten die neue Version im ______“, sagte der Chef der Firma.",
        # A short span beside a speech verb.
        "The CEO said “absolutely not” about the merger with ______ last week.",
        "The Hub maintainer wrote «никогда» about storing ______ in the cache.",
    ],
)
def test_masked_quotation_is_rejected(sentence: str) -> None:
    question = f"Fill in the blank: {sentence}"
    assert reject_reason(question, DOC, task_type="extractive") == "a quote"


@pytest.mark.parametrize(
    "sentence",
    [
        'Set the mode to "auto" before ______ restarts the Space container.',
        "Apple calls the feature “Live Text”, launched in ______.",
        'The setting labelled "______ mode" controls the Hub cache size.',
        "Компания назвала функцию «Живой текст» в ______ году.",
        "Apple nennt die Funktion „Live Text“ seit dem Jahr ______.",
        "Apple nennt die Funktion »Live Text« seit dem Jahr ______.",
    ],
)
def test_masked_quoted_term_is_kept(sentence: str) -> None:
    """A short quoted name is a term, not someone's wording."""
    question = f"Fill in the blank: {sentence}"
    assert reject_reason(question, DOC, task_type="extractive") is None


def test_masked_blank_is_no_anchor() -> None:
    """A hidden name does not tell the reader who "it" is."""
    masked = "Fill in the blank: It listens on port ______ inside the container."
    assert reject_reason(masked, DOC, task_type="extractive") is not None


def test_llm_masking_uses_each_sentence_once() -> None:
    sentence = "The Hub stores endpoint metadata in {} for {} Space."
    data = {
        "named_entity": [
            {"question": sentence.format("______", "every"), "answer": "Postgres"}
        ],
        "numeric": [
            {"question": sentence.format("Postgres", "______"), "answer": "every"}
        ],
    }
    out = parse_combined(data, ("named_entity", "numeric"))
    assert len(out["named_entity"]) == 1 and out["numeric"] == []


def test_masked_stub_is_rejected() -> None:
    assert reject_reason("Fill in the blank: ______.", DOC, task_type="extractive")


def test_mask_is_required() -> None:
    assert reject_reason("Which port is used?", DOC, task_type="extractive")


def test_choice_skips_the_single_answer_rules() -> None:
    """The options themselves make the question unambiguous."""
    question = "Name one of the ports the Space exposes"
    assert reject_reason(question, DOC, task_type="choice") is None
    assert reject_reason(question, DOC, task_type="abstractive") is not None


def test_statement_still_must_stand_alone() -> None:
    assert reject_reason("This decision was reversed", DOC, task_type="statement")


# --- markup is not masked --------------------------------------------------


def test_code_and_diagrams_are_not_prose() -> None:
    """LiveTruth worked over news, our corpus is documentation with code in it."""
    assert not is_prose("```python")
    assert not is_prose("| slug | port |")
    assert not is_prose("C->>MW: POST /endpoints/{slug}/query")
    assert not is_prose("- benchmarks_mode: off")


def test_ordinary_sentence_is_prose() -> None:
    assert is_prose("The Hub stores endpoint metadata but never the documents.")


def test_answer_shape_rejects_markup_spans() -> None:
    """A shard of markup such as "+ vector" is not a gold answer."""
    data = {
        "temporal": [
            {"question": "Datasets and ______ stores are shown.", "answer": "+ vector"},
            {"question": "Released on ______ after review.", "answer": "2026-09-08"},
        ]
    }
    parsed = parse_combined(data, ("temporal",))
    assert [m.answer for m in parsed["temporal"]] == ["2026-09-08"]


def test_answer_left_inside_the_question_is_dropped() -> None:
    """A reference answer left inside the text makes the item pointless."""
    data = {
        "numeric": [
            {"question": "It listens on ______, that is 8100.", "answer": "8100"}
        ]
    }
    assert parse_combined(data, ("numeric",))["numeric"] == []


# --- the abstractive ones --------------------------------------------------


def test_ttil_builds_a_lettered_choice() -> None:
    items = [
        {"statement": "The Hub keeps endpoint metadata.", "label": "truth"},
        {"statement": "The Hub keeps the documents themselves.", "label": "lie"},
        {"statement": "A Space can serve several endpoints.", "label": "truth"},
    ]
    pairs, rejected = clean_ttil(items, 1, DOC)
    assert not rejected
    # The reference answer points at the lie wherever the shuffle put it.
    assert pairs[0].answer.endswith("The Hub keeps the documents themselves.")
    letter = pairs[0].answer[0]
    assert f"{letter}) The Hub keeps the documents themselves." in pairs[0].question
    assert len(pairs[0].distractors) == 2
    # It is the true statements that are checked for support in the source, not
    # the lie: a good lie is bound to contradict the source.
    assert pairs[0].meta["claims"] == pairs[0].distractors


def test_ttil_needs_exactly_one_lie() -> None:
    items = [
        {"statement": "One.", "label": "lie"},
        {"statement": "Two.", "label": "lie"},
        {"statement": "Three.", "label": "truth"},
    ]
    pairs, rejected = clean_ttil(items, 1, DOC)
    assert not pairs
    assert "lie" in rejected[0]


def test_multihop_requires_two_facts() -> None:
    """Fewer than two facts is an ordinary question, and multihop is no place for it."""
    items = [
        {
            "question": "How does satellite registration affect endpoint URLs?",
            "answer": "The satellite provides the origin the URL is built from.",
            "hop_facts": ["satellites carry base_url", "endpoints link to a space"],
        },
        {
            "question": "Which database does the Hub use?",
            "answer": "PostgreSQL.",
            "hop_facts": ["one fact only"],
        },
    ]
    pairs, rejected = clean_multihop(items, 4, DOC)
    assert len(pairs) == 1
    assert "fewer than two facts" in rejected[0]


_TIERED = {
    "topic": "how a Space publishes an endpoint",
    "key_facts": ["one", "two", "three", "four", "five", "six"],
    "tiers": [
        {"tier": "eli5", "explanation": "A shop puts a sign in the window."},
        {"tier": "eli10", "explanation": "The Space tells the Hub about it."},
        {"tier": "eli18", "explanation": "Publication registers the endpoint."},
    ],
}


def test_tiered_keeps_one_level_with_the_shared_facts() -> None:
    pairs, rejected = clean_tiered([_TIERED], 1, DOC)
    assert not rejected
    assert len(pairs) == 1
    meta = pairs[0].meta
    assert meta["tier"] in {"eli5", "eli10", "eli18"}
    assert meta["grading"] == "key_facts"
    # Capped at five, the same for every level.
    assert meta["key_facts"] == ["one", "two", "three", "four", "five"]


def test_tiered_level_is_random_and_reproducible() -> None:
    """Seeded from the topic by default; an injected generator picks otherwise."""
    first = clean_tiered([_TIERED], 1, DOC)[0][0].meta["tier"]
    assert all(
        clean_tiered([_TIERED], 1, DOC)[0][0].meta["tier"] == first for _ in range(5)
    )
    picked = {
        clean_tiered([_TIERED], 1, DOC, rng=random.Random(seed))[0][0].meta["tier"]
        for seed in range(30)
    }
    assert picked == {"eli5", "eli10", "eli18"}


def test_tiered_prompt_asks_for_shared_exclusive_facts() -> None:
    prompt = GENERATORS["tiered_explanation"].system.format(n=1)
    assert "short neutral subject" in prompt
    assert "List 3 to 5 key facts" in prompt
    assert "same key facts for every audience level" in prompt
    assert '"key_facts": [' in prompt and "{{" not in prompt


def test_tiered_falls_back_to_a_levels_own_facts() -> None:
    payload = {
        "topic": "publication",
        "tiers": [
            {
                "tier": "eli10",
                "explanation": "The Space tells the Hub about it.",
                "key_facts": ["the Hub is told"],
            }
        ],
    }
    pairs, _ = clean_tiered([payload], 1, DOC)
    assert pairs[0].meta["key_facts"] == ["the Hub is told"]


def test_tiered_level_without_facts_is_unjudgeable() -> None:
    """Without key facts there is nothing to judge the item by."""
    payload = {
        "topic": "publication",
        "tiers": [
            {
                "tier": "eli5",
                "explanation": "A long enough explanation here.",
                "key_facts": [],
            }
        ],
    }
    pairs, rejected = clean_tiered([payload], 1, DOC)
    assert not pairs
    assert "key facts" in rejected[0]


# --- rejecting reference answers by their claims ---------------------------


def test_claims_are_checked_not_the_prose() -> None:
    """An explanation for a five-year-old is bound to sound unlike the source.

    What is checked is not its text but the facts it rests on.
    """
    fragment = (
        "The Hub stores endpoint metadata in PostgreSQL. "
        "A Space serves several endpoints."
    )
    facts = ["the Hub stores metadata in PostgreSQL", "a Space serves endpoints"]
    assert review_claims(facts, fragment).grounded


def test_invented_claims_are_caught() -> None:
    fragment = "The Hub stores endpoint metadata in PostgreSQL."
    invented = ["OMSyft records an electrocardiogram", "doctors read the output"]
    assert not review_claims(invented, fragment).grounded


def test_no_claims_is_not_grounded() -> None:
    assert not review_claims([], "any fragment").grounded


# --- language --------------------------------------------------------------
# The German text below is a fixture, not prose of ours: language detection can
# only be checked with text in the language being detected.


def test_language_detection_separates_the_candidates() -> None:
    english = (
        "The Hub stores endpoint metadata but it never stores the documents "
        "themselves, and that is the whole point of the design."
    )
    german = (
        "Der Hub speichert nur die Beschreibungen der Endpunkte, aber niemals "
        "die Dokumente selbst, und genau darin liegt der Sinn des Entwurfs."
    )
    assert detect_language(english, ("en", "de")) == "en"
    assert detect_language(german, ("en", "de")) == "de"


def test_too_short_to_judge() -> None:
    assert detect_language("Hub stores", ("en", "ru")) is None


_ENGLISH_ARTICLE = (
    "Acme raised forty million dollars in a Series B round that was led by "
    "Sequoia in March, and the company said it will spend most of the money on "
    "hiring engineers for its new office in Lisbon over the next two years."
)


def _pair(question: str, answer: str) -> Pair:
    return Pair(question=question, answer=answer, distractors=[], meta={})


def test_a_question_in_another_language_is_dropped() -> None:
    """An Italian question out of an English article is rejected."""
    from syft_benchmark.generation.pipeline import (
        WRONG_LANGUAGE,
        _drop_wrong_language,
    )

    english = _pair(
        "How much did Acme raise in the Series B round that was led by Sequoia?",
        "Forty million dollars, most of it for hiring engineers.",
    )
    italian = _pair(
        "Quanto ha raccolto Acme nel suo round di Serie B guidato da Sequoia?",
        "Quaranta milioni di dollari, per la maggior parte per assumere ingegneri.",
    )
    good, bad = _drop_wrong_language([english, italian], _ENGLISH_ARTICLE)
    assert good == [english]
    assert [r.drop for r in bad] == [WRONG_LANGUAGE]
    assert bad[0].note == "wrong language: it, the article en"


def test_too_short_to_tell_the_language_is_kept() -> None:
    """Detection gives no verdict on a short pair, and no verdict is no reject."""
    from syft_benchmark.generation.pipeline import _drop_wrong_language

    short = _pair("Chi guida Acme?", "Mario Rossi.")
    good, bad = _drop_wrong_language([short], _ENGLISH_ARTICLE)
    assert good == [short]
    assert bad == []


_RUSSIAN_ARTICLE = (
    "Компания Акме привлекла сорок миллионов долларов в раунде, который возглавил "
    "фонд Секвойя в марте, и в компании сказали, что потратят большую часть денег "
    "на наём инженеров для нового офиса в Лиссабоне в течение двух лет."
)
_GERMAN_ARTICLE = (
    "Die Firma Acme hat vierzig Millionen Dollar in einer Runde eingesammelt, die "
    "von Sequoia im März geführt wurde, und das Geld soll vor allem für neue "
    "Ingenieure in dem Büro in Lissabon in den nächsten zwei Jahren dienen."
)


def test_fixed_english_wording_does_not_decide_the_language() -> None:
    """Items in the article's language are kept despite the English around them."""
    from syft_benchmark.generation.negative import clean_unanswerable
    from syft_benchmark.generation.pipeline import (
        _drop_wrong_language,
        _masked_to_pairs,
    )

    statements = [
        {"statement": "Акме привлекла сорок миллионов долларов.", "label": "truth"},
        {"statement": "Раунд возглавил фонд Секвойя.", "label": "truth"},
        {"statement": "Новый офис откроют в Мадриде.", "label": "lie"},
    ]
    ttil, _ = clean_ttil(statements, 1, _RUSSIAN_ARTICLE)
    masked = parse_combined(
        {
            "named_entity": [
                {
                    "question": "Новый офис компании Акме для инженеров откроют в "
                    "городе ______ в течение двух лет.",
                    "answer": "Лиссабоне",
                }
            ]
        },
        ("named_entity",),
    )["named_entity"]
    blanks, _ = _masked_to_pairs(masked, _RUSSIAN_ARTICLE)
    assert ttil and blanks
    good, bad = _drop_wrong_language(ttil + blanks, _RUSSIAN_ARTICLE)
    assert good == ttil + blanks and bad == []

    tiered, _ = clean_tiered(
        [
            {
                "topic": "Die Finanzierung von Acme",
                "tiers": [
                    {
                        "tier": "eli5",
                        "explanation": "Acme hat viel Geld bekommen, und die Firma "
                        "will damit mehr Leute für ihr neues Büro einstellen.",
                        "key_facts": ["Acme hat vierzig Millionen Dollar eingesammelt"],
                    }
                ],
            }
        ],
        1,
        _GERMAN_ARTICLE,
    )
    absent, _ = clean_unanswerable(
        [
            {
                "question": "Wie viele Ingenieure will Acme in dem Büro in Lissabon "
                "einstellen?",
                "missing": "die Zahl der Ingenieure",
            }
        ],
        1,
        _GERMAN_ARTICLE,
    )
    assert tiered and absent
    good, bad = _drop_wrong_language(tiered + absent, _GERMAN_ARTICLE)
    assert good == tiered + absent and bad == []


def test_a_choice_in_another_language_is_dropped() -> None:
    """Option letters do not save a French multiple choice from an English article."""
    from syft_benchmark.generation.pipeline import WRONG_LANGUAGE, _drop_wrong_language

    french = Pair(
        question="Qui a mené le tour de table de la série B de Acme ?\n"
        "  A) Sequoia\n  B) Accel\n  C) Index\n  D) Benchmark",
        answer="A) Sequoia, qui a mené le tour en mars pour la société",
        distractors=["B) Accel", "C) Index", "D) Benchmark"],
        meta={},
    )
    good, bad = _drop_wrong_language([french], _ENGLISH_ARTICLE)
    assert good == [] and [r.drop for r in bad] == [WRONG_LANGUAGE]


def test_rules_are_numbered_without_gaps() -> None:
    """Prompts that continue a shared rule list keep its numbering."""
    from syft_benchmark.generation.generators import _MCQ_SYSTEM, _QA_SYSTEM
    from syft_benchmark.generation.negative import (
        FALSE_PREMISE_SYSTEM,
        UNANSWERABLE_SYSTEM,
    )

    for system in (_QA_SYSTEM, _MCQ_SYSTEM, FALSE_PREMISE_SYSTEM, UNANSWERABLE_SYSTEM):
        numbers = [int(n) for n in re.findall(r"^(\d+)\. ", system, re.MULTILINE)]
        assert numbers == list(range(1, len(numbers) + 1))
    assert "exactly ONE missing detail" in UNANSWERABLE_SYSTEM


def test_writers_ask_about_facts_only_this_story_has() -> None:
    """Open, multiple-choice, connect-the-facts and false-claim writers."""
    from syft_benchmark.generation.abstractive import MULTIHOP_SYSTEM, TTIL_SYSTEM
    from syft_benchmark.generation.extractive import COMBINED_SYSTEM
    from syft_benchmark.generation.generators import _MCQ_SYSTEM, _QA_SYSTEM

    def flat(system: str) -> str:
        return " ".join(system.format(n=2).split())

    rule = "Build each question on a fact that only this story reports"
    for system in (_QA_SYSTEM, _MCQ_SYSTEM, MULTIHOP_SYSTEM, TTIL_SYSTEM):
        assert rule in flat(system)
    assert "each must be contradicted by it" in flat(_MCQ_SYSTEM)
    assert "a detail only this story reports, so the web can't" in flat(TTIL_SYSTEM)
    assert (
        flat(COMBINED_SYSTEM)
        .split(" Respond with ONLY")[0]
        .endswith("- Use each sentence once.")
    )


def test_generation_calls_the_generator_role_not_the_common_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The generator goes to ITS OWN provider.

    A separately configured generator provider takes effect: the role reaches
    chat, not the shared address.
    """
    from syft_benchmark.config import Settings
    from syft_benchmark.generation import pipeline
    from syft_benchmark.llm import Provider
    from syft_benchmark.sources import Chunk, Document

    seen: dict[str, object] = {}

    def fake_chat(*args: object, **kwargs: object) -> tuple[str, dict[str, object]]:
        seen.update(kwargs)
        return "[]", {}

    monkeypatch.setattr(pipeline, "chat", fake_chat)

    chunk = Chunk(
        chunk_id="c1",
        doc_id="d1",
        chunk_index=0,
        text="A short fragment of text.",
        file_name="doc.md",
        headings="Doc",
    )
    document = Document(
        doc_id="d1",
        title="Doc",
        url="",
        source="local_file",
        file_name="doc.md",
        chunks=[chunk],
    )
    role = Provider(
        role="generator",
        url="http://ollama:11434/v1",
        api_key="",
        model="some-generator",
    )

    pipeline._run_llm_generator(
        GENERATORS["qa"],
        document,
        chunk,
        Settings(spaces_file="config/spaces.json"),  # type: ignore[arg-type]
        role,
    )

    assert seen.get("provider") is role
