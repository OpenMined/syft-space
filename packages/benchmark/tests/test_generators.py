"""The eight generators: rejection, parsing and the bounds of applicability."""

from __future__ import annotations

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
from syft_benchmark.generation.language import detect_language, spacy_available

DOC = "Space registers with the Hub. The Hub stores endpoint metadata."

# spaCy is an optional extra, and its absence is a working mode rather than a
# broken install: without it the extractive generators go through an LLM. So a
# check of what spaCy does has nothing to say when spaCy is not there, and
# failing would report a fault that is not one.
needs_spacy = pytest.mark.skipif(
    not spacy_available(), reason="spaCy is an optional extra and is not installed"
)


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


def test_masked_sentence_survives_its_own_pronouns() -> None:
    """The main reason the rules are split by item type.

    In a masked sentence a pronoun stands legitimately: its antecedent is right
    there, in the same sentence. The rules for a free-form question would have
    cut it down.
    """
    masked = "Fill in the blank: It listens on port ______ inside the container."

    assert reject_reason(masked, DOC, task_type="extractive") is None
    assert reject_reason(masked, DOC, task_type="abstractive") is not None


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
    """On technical texts spaCy marks "+ vector" as a date."""
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


def test_tiered_expands_into_three_levels() -> None:
    payload = {
        "topic": "how a Space publishes an endpoint",
        "tiers": [
            {
                "tier": "eli5",
                "explanation": "A shop puts a sign in the window.",
                "key_facts": ["a Space publishes"],
            },
            {
                "tier": "eli10",
                "explanation": "The Space tells the Hub about it.",
                "key_facts": ["the Hub is told"],
            },
            {
                "tier": "eli18",
                "explanation": "Publication registers the endpoint.",
                "key_facts": ["registration"],
            },
        ],
    }
    pairs, rejected = clean_tiered([payload], 1, DOC)
    assert not rejected
    assert [p.meta["tier"] for p in pairs] == ["eli5", "eli10", "eli18"]
    assert all(p.meta["grading"] == "key_facts" for p in pairs)


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


@needs_spacy
def test_language_detection_separates_the_installed_ones() -> None:
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


def test_generation_calls_the_generator_role_not_the_common_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The generator goes to ITS OWN provider.

    The call used to go to the shared address, and a separately configured
    generator provider silently did not apply: it could be set but could not
    take effect. What we check is exactly that the role reaches chat.
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
