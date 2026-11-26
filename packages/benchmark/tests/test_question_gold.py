"""The question's gold: source article, supporting text, article fingerprint."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from syft_benchmark.config import SpaceConfig, get_settings
from syft_benchmark.db import QaPair, session_scope
from syft_benchmark.generation import gold, pipeline
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Pair
from syft_benchmark.sources import Chunk, Document, load_documents, text_fingerprint
from syft_benchmark.sources.chroma import FINGERPRINT_SCHEME

SPACE = "pytest-gold"

FIRST = (
    "The Harbourton council voted 7 to 2 on March 3, 2026 to restore the old "
    "lighthouse. Mayor Ana Ruiz said the work would cost $4.2 million. "
    "The U.S. Coast Guard will inspect the lamp in June."
)
SECOND = (
    "Repairs start in April and should take 18 months. The contractor, "
    "Brightwater Ltd., won the tender against three rivals. Local fishermen "
    "welcomed the decision."
)


def _chunk(index: int, text: str) -> Chunk:
    return Chunk(
        chunk_id=f"d1_{index}",
        doc_id="d1",
        chunk_index=index,
        text=text,
        file_name="lighthouse.md",
        headings="",
    )


DOC = Document(
    doc_id="d1",
    title="Lighthouse",
    url="",
    source="",
    file_name="lighthouse.md",
    chunks=[_chunk(0, FIRST), _chunk(1, SECOND)],
    absolute_path="/docs/lighthouse.md",
    fingerprint=text_fingerprint([FIRST, SECOND]),
)


def _gold(
    key: str, question: str, answer: str, chunk_id: str = "d1_0", **meta: Any
) -> dict[str, Any]:
    return gold.build_gold(
        key,
        question,
        answer,
        meta,
        DOC,
        chunk_id,
        control=GENERATORS[key].is_control,
    )


def _passages(item: dict[str, Any]) -> list[str]:
    return [p["text"] for p in item["passages"]]


# --- the article --------------------------------------------------------------


def test_the_article_is_named_by_file_path_id_and_fingerprint() -> None:
    found = _gold("qa", "How much will the lighthouse cost?", "$4.2 million.")

    (article,) = found["articles"]
    assert article["file_name"] == "lighthouse.md"
    assert article["absolute_path"] == "/docs/lighthouse.md"
    assert article["doc_id"] == "d1"
    assert article["fingerprint"] == {
        "scheme": FINGERPRINT_SCHEME,
        "sha256": DOC.fingerprint,
    }
    assert article["chunk_ids"] == ["d1_0"]


# --- the evidence, by kind ------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "question", "answer"),
    [
        (
            "named_entity_masking",
            "Fill in the blank: Mayor ______ said the work would cost $4.2 million.",
            "Ana Ruiz",
        ),
        (
            "numeric_masking",
            "Fill in the blank: Mayor Ana Ruiz said the work would cost ______.",
            "$4.2 million",
        ),
        (
            "temporal_masking",
            "Fill in the blank: The Harbourton council voted 7 to 2 on ______ to "
            "restore the old lighthouse.",
            "March 3, 2026",
        ),
    ],
)
def test_a_masked_sentence_is_found_verbatim(
    key: str, question: str, answer: str
) -> None:
    (item,) = _gold(key, question, answer)["evidence"]

    assert item["role"] == gold.ANSWER
    assert item["match"] == gold.EXACT
    (passage,) = _passages(item)
    assert answer in passage and passage in FIRST


def test_a_reworded_free_answer_is_found_by_its_words() -> None:
    (item,) = _gold(
        "qa",
        "How much did Mayor Ana Ruiz say restoring the Harbourton lighthouse "
        "would cost?",
        "Ana Ruiz said the restoration would cost $4.2 million.",
    )["evidence"]

    assert item["match"] == gold.OVERLAP
    assert _passages(item) == ["Mayor Ana Ruiz said the work would cost $4.2 million."]


def test_the_correct_option_is_found_and_the_letter_dropped() -> None:
    (item,) = _gold(
        "mcq",
        "How many rivals did Brightwater Ltd. beat for the tender?\n  A) two\n"
        "  B) three\n  C) five\n  D) six",
        "B) three",
        chunk_id="d1_1",
    )["evidence"]

    assert item["target"] == "three"
    assert _passages(item) == [
        "The contractor, Brightwater Ltd., won the tender against three rivals."
    ]


def test_two_truths_one_lie_locates_the_altered_detail_and_the_truths() -> None:
    evidence = _gold(
        "two_truths_one_lie",
        "One of the following three statements is FALSE.",
        "C) The Harbourton council voted 9 to 0 to restore the lighthouse.",
        source_detail="voted 7 to 2 on March 3, 2026",
        claims=[
            "Mayor Ana Ruiz put the cost of the work at $4.2 million.",
            "The U.S. Coast Guard is to inspect the lighthouse lamp in June.",
        ],
    )["evidence"]

    assert [e["role"] for e in evidence] == [gold.ANSWER, gold.CLAIM, gold.CLAIM]
    assert evidence[0]["match"] == gold.EXACT
    assert _passages(evidence[2]) == [
        "The U.S. Coast Guard will inspect the lamp in June."
    ]


def test_every_hop_is_located_in_its_own_chunk() -> None:
    found = _gold(
        "multihop_synthesis",
        "How long after the Harbourton vote will the lighthouse repairs end?",
        "About two years.",
        chunk_id="doc:d1",
        hop_facts=[
            "The Harbourton council voted on March 3, 2026 to restore the lighthouse",
            "Repairs start in April and take 18 months",
        ],
    )

    hops = found["evidence"]
    assert [h["role"] for h in hops] == [gold.HOP, gold.HOP]
    assert [p["chunk_id"] for h in hops for p in h["passages"]] == ["d1_0", "d1_1"]
    assert found["articles"][0]["chunk_ids"] == ["d1_0", "d1_1"]


def test_a_key_fact_not_in_the_article_is_kept_unlocated() -> None:
    facts = _gold(
        "tiered_explanation",
        "Explain this.\n\nTopic: The Harbourton lighthouse restoration",
        "A long explanation.",
        chunk_id="doc:d1",
        key_facts=[
            "Brightwater Ltd. won the tender against three rivals",
            "The lighthouse was built by Portuguese sailors in 1702",
        ],
    )["evidence"]

    assert facts[0]["match"] == gold.OVERLAP
    assert facts[1] == {
        "role": gold.KEY_FACT,
        "target": "The lighthouse was built by Portuguese sailors in 1702",
        "match": gold.NONE,
        "coverage": facts[1]["coverage"],
        "passages": [],
    }


def test_an_unanswerable_question_keeps_its_article_and_no_evidence() -> None:
    found = _gold(
        "unanswerable_property",
        "What colour will the Harbourton lighthouse be painted?",
        "not in the corpus: the colour",
    )

    assert found["control"] is True
    assert found["evidence"] == []
    assert found["articles"][0]["file_name"] == "lighthouse.md"


def test_a_false_premise_is_control_with_its_corrections_located() -> None:
    found = _gold(
        "false_premise",
        "Why did the Harbourton council reject the lighthouse restoration?",
        "It did not: the council voted 7 to 2 to restore it.",
        claims=["The council voted 7 to 2 to restore the old lighthouse"],
    )

    assert found["control"] is True
    (item,) = found["evidence"]
    assert item["role"] == gold.CORRECTION
    assert _passages(item)[0].startswith("The Harbourton council voted 7 to 2")


# --- matching and the fingerprint --------------------------------------------


def test_sentences_keep_abbreviations_and_closing_quotes() -> None:
    text = (
        "“A genius,” the poet W. H. Auden said. The U.S. agreed on Nov. 8 "
        "with Brightwater Co. officials.\nNext line"
    )

    assert gold.sentences(text) == [
        "“A genius,” the poet W. H. Auden said.",
        "The U.S. agreed on Nov. 8 with Brightwater Co. officials.",
        "Next line",
    ]


@pytest.mark.parametrize(
    ("key", "question", "answer", "meta"),
    [
        ("qa", "How much will the lighthouse cost?", "$4.2 million.", {}),
        (
            "named_entity_masking",
            "Fill in the blank: Mayor ______ said the work would cost $4.2 million.",
            "Ana Ruiz",
            {},
        ),
        (
            "multihop_synthesis",
            "Who builds the lighthouse and when does work start?",
            "Brightwater Ltd., from April.",
            {
                "hop_facts": [
                    "Repairs start in April",
                    "Brightwater Ltd. won the tender",
                ]
            },
        ),
    ],
)
def test_every_located_passage_is_verbatim_in_its_chunk(
    key: str, question: str, answer: str, meta: dict[str, Any]
) -> None:
    chunk_id = "doc:d1" if key == "multihop_synthesis" else "d1_0"
    texts = {c.chunk_id: c.text for c in DOC.chunks}
    found = _gold(key, question, answer, chunk_id, **meta)

    passages = [p for e in found["evidence"] for p in e["passages"]]
    assert passages
    for p in passages:
        assert p["text"] in texts[p["chunk_id"]]


def test_the_fingerprint_ignores_chunking_but_not_the_words() -> None:
    whole = text_fingerprint([FIRST + "\n\n" + SECOND])

    assert text_fingerprint([FIRST, SECOND]) == whole
    assert text_fingerprint([FIRST[:50], FIRST[50:] + " ", SECOND]) == whole
    assert text_fingerprint([FIRST.replace("7 to 2", "7 to 3"), SECOND]) != whole


def test_the_fingerprint_ignores_the_overlap_between_chunks() -> None:
    """With overlap, a chunk starts with the previous one's tail and a newline."""
    tail = "The U.S. Coast Guard will inspect the lamp in June."
    overlapped = [FIRST, f"{tail}\n{SECOND}"]

    assert text_fingerprint(overlapped) == text_fingerprint([FIRST, SECOND])


class _Client:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    def iter_chunks(self, _collection_id: str) -> Any:
        yield from self.chunks


def test_loading_fingerprints_every_chunk_and_keeps_the_path() -> None:
    header = 'title: "Lighthouse"\nsource: "Gazette"\n---\n'
    banner = "We use cookie files. Accept cookie files. More cookie consent."
    chunks = [
        Chunk(
            chunk_id=f"d1_{i}",
            doc_id="d1",
            chunk_index=i,
            text=text,
            file_name="lighthouse.md",
            headings="",
            absolute_path="/docs/lighthouse.md",
        )
        for i, text in enumerate([header + FIRST, SECOND, banner])
    ]

    (doc,) = load_documents(_Client(chunks), "c", min_chars=0)  # type: ignore[arg-type]

    assert doc.absolute_path == "/docs/lighthouse.md"
    # The header is not article text; the boilerplate chunk is.
    assert len(doc.chunks) == 2
    assert doc.fingerprint == text_fingerprint([FIRST, SECOND, banner])


# --- persistence -----------------------------------------------------------------


@pytest.mark.needs_db
def test_the_gold_is_stored_with_the_question(clean: None) -> None:
    conf = get_settings()
    space = SpaceConfig(key=SPACE, url="http://space", endpoint="e")
    pair = Pair(
        question=(
            "Fill in the blank: Mayor ______ said the work would cost $4.2 million."
        ),
        answer="Ana Ruiz",
        distractors=[],
        meta={"category": "named_entity"},
    )

    (row,) = pipeline._store(
        space,
        DOC,
        "d1_0",
        FIRST,
        [pair],
        GENERATORS["named_entity_masking"],
        "gen/m",
        "coll",
        pipeline.GenerationReport(space=SPACE),
        conf=conf,
    )

    with session_scope(conf) as session:
        stored = session.scalars(select(QaPair).where(QaPair.id == row.id)).one()
        found = stored.meta[gold.META]
    assert found["version"] == gold.VERSION
    assert found["control"] is False
    assert found["articles"][0]["file_name"] == "lighthouse.md"
    assert found["evidence"][0]["passages"] == [
        {
            "text": "Mayor Ana Ruiz said the work would cost $4.2 million.",
            "chunk_id": "d1_0",
        }
    ]
