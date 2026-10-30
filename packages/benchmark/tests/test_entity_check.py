"""The entity check: a question whose subject the question alone does not
identify is rejected as written.

One extra call to the question writer per unit, in a fresh conversation, with
the unit's questions only. A failed call keeps the questions.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy import select

from syft_benchmark.config import PairStatus, Settings, SpaceConfig, StatusReason
from syft_benchmark.db import Job, QaPair, session_scope
from syft_benchmark.generation import decisions, entities, pipeline
from syft_benchmark.generation.abstractive import TTIL_HEAD
from syft_benchmark.generation.extractive import COMBINED_SYSTEM, FILL_IN_PREFIX
from syft_benchmark.generation.generators import GENERATORS
from syft_benchmark.generation.pair import Pair
from syft_benchmark.llm import LLMError, Provider, cost
from syft_benchmark.report import export_xlsx, filter_view
from syft_benchmark.sources import Chunk, Document

from fakes import ChromaStub

SPACE = "pytest-entity-check"
JOB = "pytest-entity-job"

MARIAM_MCQ = (
    "Mariam, who asked to be identified only by her first name out of fear of "
    "online retaliation, administers a Facebook group for women in which "
    "country?\n  A) The United Arab Emirates\n  B) Saudi Arabia\n  C) Egypt\n"
    "  D) Pakistan"
)
MARIAM_QA = (
    "What action did Mariam take after the volume and nature of messages from "
    "strangers became impossible to ignore while running her nearly "
    "400,000-member women's Facebook group?"
)
ITALIAN_QA = (
    "Quale tariffa ha annunciato Donald Trump, il presidente degli Stati Uniti, "
    "sulle importazioni di acciaio dalla Cina nel suo discorso?"
)
TRUMP_QA = (
    "Which tariff rate did Donald Trump, the US president, announce on Chinese "
    "steel imports in the speech covered by Wired?"
)

ARTICLE = (
    "Mariam, who asked to be identified only by her first name out of fear of "
    "online retaliation, runs a Facebook group for women in Egypt with nearly "
    "400,000 members. When the volume and nature of the messages from strangers "
    "became impossible to ignore, she turned off direct messages for the group "
    "and asked the moderators to screen every new member by hand. Donald Trump, "
    "the US president, announced a tariff of 50 percent on Chinese steel imports."
)

REPLY = json.dumps(
    [
        {
            "index": 1,
            "entities": [
                {
                    "name": "Mariam",
                    "identifiable": False,
                    "why": "first name only",
                },
                {"name": "Facebook", "identifiable": True, "why": "the platform"},
            ],
            "ok": False,
        },
        {
            "index": 2,
            "entities": [
                {"name": "Mariam", "identifiable": False, "why": "first name only"}
            ],
            "ok": False,
        },
        {
            "index": 3,
            "entities": [
                {"name": "Donald Trump", "identifiable": True, "why": "full name"}
            ],
            "ok": True,
        },
    ]
)

PROVIDER = Provider(
    role="generator", url="http://ollama:11434/v1", api_key="", model="w"
)


def _settings(**kwargs: Any) -> Settings:
    base: dict[str, Any] = {
        "document_window_days": 0,
        "pairs_per_chunk": 3,
        "max_consecutive_failures": 5,
        "entity_check": True,
    }
    return Settings(**{**base, **kwargs})


def _pair(question: str) -> Pair:
    return Pair(question=question, answer="Egypt.", distractors=[], meta={})


class _Checker:
    """The entity check call, stubbed: what it was asked, what it says."""

    def __init__(self, reply: str | Exception = REPLY) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self, system: str, user: str, **kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        self.calls.append({"system": system, "user": user, **kwargs})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply, {"cost_usd": 0.002, "latency_s": 1.234}


# --- the writer prompts ------------------------------------------------------


def _flat(system: str) -> str:
    return " ".join(system.format(n=2).split())


# Every writer's prompt as the registry hands it to the model; the fill-in
# kinds share the combined prompt.
WRITER_PROMPTS = {key: spec.system for key, spec in GENERATORS.items() if spec.system}
WRITER_PROMPTS["fill_in"] = COMBINED_SYSTEM


@pytest.mark.parametrize("writer", sorted(WRITER_PROMPTS))
def test_every_writer_asks_for_identifiable_names(writer: str) -> None:
    system = WRITER_PROMPTS[writer]
    flat = _flat(system)
    assert "identifiable without the story" in flat
    assert "full name plus role or affiliation" in flat
    assert "first name, a pseudonym or an anonymous source" in flat


# --- what the check sees and reads -------------------------------------------


def test_the_check_sees_the_sentence_the_topic_and_the_statements() -> None:
    blank = Pair(
        question=f"{FILL_IN_PREFIX} Mariam runs a group in ______.",
        answer="Egypt",
        distractors=[],
        meta={},
    )
    tiered = Pair(
        question="Explain this.\n\nTopic: Mariam's group",
        answer="...",
        distractors=[],
        meta={"topic": "Mariam's group"},
    )
    ttil = Pair(
        question=f"{TTIL_HEAD}\n  A) One.\n  B) Two.\n  C) Three.",
        answer="A) One.",
        distractors=[],
        meta={},
    )
    assert entities.shown("named_entity_masking", blank) == (
        "Mariam runs a group in ______."
    )
    assert entities.shown("tiered_explanation", tiered) == "Topic: Mariam's group"
    assert entities.shown("two_truths_one_lie", ttil).startswith("Statements:")
    assert TTIL_HEAD not in entities.shown("two_truths_one_lie", ttil)
    assert "D) Pakistan" in entities.shown("mcq", _pair(MARIAM_MCQ))


def test_the_reply_is_parsed_by_question() -> None:
    verdicts = entities.parse(REPLY, 3)
    assert [verdicts[i].ok for i in range(3)] == [False, False, True]
    assert verdicts[0].note() == "ambiguous entity: Mariam (first name only)"


def test_a_reply_out_of_range_or_unreadable_is_no_verdict() -> None:
    assert entities.parse('[{"index": 9, "ok": false}, {"index": 1, "ok": true}]', 2)
    with pytest.raises(LLMError):
        entities.parse("I cannot tell.", 2)
    with pytest.raises(LLMError):
        entities.parse('[{"index": 5, "ok": false}]', 2)


# --- the check on a unit ------------------------------------------------------


def test_the_mariam_questions_are_rejected_and_trump_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(pipeline, "chat", checker)
    # The screen is one step of a build; called alone, the stub sees one check.
    kept, rejected, call = pipeline._screen_entities(
        {"mcq": [_pair(MARIAM_MCQ)], "qa": [_pair(MARIAM_QA), _pair(TRUMP_QA)]},
        _settings(),
        PROVIDER,
    )

    assert [p.question for p in kept["qa"]] == [TRUMP_QA]
    assert kept["mcq"] == []
    assert [r.pair.question for r in rejected["mcq"] + rejected["qa"]] == [
        MARIAM_MCQ,
        MARIAM_QA,
    ]
    for item in rejected["mcq"] + rejected["qa"]:
        assert item.reason is StatusReason.AMBIGUOUS_ENTITY
        assert item.drop == pipeline.AMBIGUOUS_ENTITY == "ambiguous entity"
        assert item.note.startswith("ambiguous entity: Mariam")
        assert item.pair.meta[entities.META]["outcome"] == decisions.REMOVED
    assert kept["qa"][0].meta[entities.META]["outcome"] == decisions.KEPT

    # One call, to the writer, in a fresh conversation with the questions only.
    (asked,) = checker.calls
    assert asked["provider"] is PROVIDER
    assert asked["role"] == cost.WRITER
    assert "messages" not in asked and not asked.get("web_search")
    assert asked["system"] == entities.SYSTEM
    assert MARIAM_MCQ in asked["user"] and TRUMP_QA in asked["user"]
    assert "turned off direct messages" not in asked["user"]
    assert call["model"] == "w" and call["reply"] == REPLY
    assert call["cost_usd"] == 0.002 and call["latency_s"] == 1.23


@pytest.mark.parametrize("reply", [LLMError("down"), "not json at all"])
def test_a_failed_check_keeps_the_questions(
    monkeypatch: pytest.MonkeyPatch, reply: str | Exception
) -> None:
    monkeypatch.setattr(pipeline, "chat", _Checker(reply))
    kept, rejected, _ = pipeline._screen_entities(
        {"qa": [_pair(MARIAM_QA), _pair(TRUMP_QA)]}, _settings(), PROVIDER
    )
    assert len(kept["qa"]) == 2 and rejected["qa"] == []
    for pair in kept["qa"]:
        record = pair.meta[entities.META]
        assert record["outcome"] == decisions.FAILED and record["error"]


def test_the_setting_turns_the_check_off(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = _Checker()
    monkeypatch.setattr(pipeline, "chat", checker)
    kept, rejected, call = pipeline._screen_entities(
        {"qa": [_pair(MARIAM_QA)]}, _settings(entity_check=False), PROVIDER
    )
    assert checker.calls == [] and call == {}
    assert kept["qa"][0].meta == {} and rejected["qa"] == []


# --- through a build ----------------------------------------------------------


@pytest.mark.needs_db
def test_a_build_stores_the_rejects_where_the_run_shows_them(
    monkeypatch: pytest.MonkeyPatch, clean: None
) -> None:
    chunk = Chunk(
        chunk_id="wired_0",
        doc_id="wired",
        chunk_index=0,
        text=ARTICLE,
        file_name="wired.md",
        headings="",
    )
    document = Document(
        doc_id="wired",
        title="Wired",
        url="",
        source="",
        file_name="wired.md",
        chunks=[chunk],
    )
    written = json.dumps(
        [
            {"question": MARIAM_QA, "answer": "She turned off direct messages."},
            {"question": TRUMP_QA, "answer": "A tariff of 50 percent."},
            {"question": ITALIAN_QA, "answer": "Una tariffa del 50 per cento."},
        ]
    )
    reply = json.dumps(
        [
            {
                "index": 1,
                "entities": [{"name": "Mariam", "identifiable": False}],
                "ok": False,
            },
            {"index": 2, "entities": [], "ok": True},
        ]
    )
    checker = _Checker(reply)

    def chat(system: str, user: str, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        if system == entities.SYSTEM:
            return checker(system, user, **kwargs)
        return written, {"cost_usd": 0.01}

    monkeypatch.setattr(pipeline, "ChromaClient", ChromaStub)
    monkeypatch.setattr(pipeline, "load_documents", lambda *_: [document])
    monkeypatch.setattr(pipeline, "chat", chat)
    monkeypatch.setattr(pipeline, "rotate", lambda *a, **k: _NoRotation())

    report = pipeline.generate_for_space(
        SpaceConfig(key=SPACE, url="http://space:8080", endpoint="ep"),
        generators=("qa",),
        settings=_settings(),
        job=JOB,
    )

    assert len(checker.calls) == 1
    assert report.kinds["qa"].written == 1
    assert report.kinds["qa"].dropped == {"ambiguous entity": 1, "wrong language": 1}
    assert ITALIAN_QA not in checker.calls[0]["user"]
    with session_scope() as session:
        rows = {
            row.question: row
            for row in session.execute(
                select(QaPair).where(QaPair.space == SPACE)
            ).scalars()
        }
        for row in rows.values():
            session.expunge(row)
    mariam, trump, italian = rows[MARIAM_QA], rows[TRUMP_QA], rows[ITALIAN_QA]
    assert italian.status == PairStatus.REJECTED.value
    assert italian.status_reason == StatusReason.WRONG_LANGUAGE.value
    assert mariam.status == PairStatus.REJECTED.value
    assert mariam.status_reason == StatusReason.AMBIGUOUS_ENTITY.value
    assert mariam.status_note.startswith("ambiguous entity: Mariam")
    assert trump.status == PairStatus.PENDING.value
    # The call's texts sit on one pair of the unit, its id on both.
    texts = [r.meta[entities.META] for r in (mariam, trump)]
    assert texts[0]["call"] == texts[1]["call"]
    assert sum("system" in t for t in texts) == 1

    job = Job(id=JOB, target=SPACE)
    with session_scope() as session:
        listed = filter_view.job_filter(session, job)
    by_code = {d["reason_code"]: d for d in listed["items"]}
    assert set(by_code) == {
        StatusReason.AMBIGUOUS_ENTITY.value,
        StatusReason.WRONG_LANGUAGE.value,
    }
    for decision in by_code.values():
        assert decision["stage"] == decisions.WRITING
        assert decision["outcome"] == decisions.REMOVED

    pairs = [mariam, trump]
    found = filter_view.job_decisions(pairs, JOB)
    calls = export_xlsx.recorded.check_calls(pairs, entities.META)
    calls.update(export_xlsx.recorded.writer_calls(pairs))
    # The sheet's row builder: the workbook itself is checked in test_export_xlsx.
    (sheet_row,) = export_xlsx._rejected(pairs, found, calls)
    assert sheet_row[:2] == [decisions.WRITING, StatusReason.AMBIGUOUS_ENTITY.value]
    titles = [c.title for c in export_xlsx.PAIR_COLS]
    cells = dict(zip(titles, sheet_row[3:], strict=True))
    assert cells["Entity check"] == decisions.REMOVED
    assert cells["Entity check reply"] == reply
    assert cells["Entity check cost (USD)"] == 0.002
    assert "Mariam: not identifiable" in cells["Entities"]


class _NoRotation:
    notes: list[str] = []

    def line(self) -> str:
        return ""
