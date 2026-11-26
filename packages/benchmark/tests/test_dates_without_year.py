"""A date without a year in a question gets the year from the publish date, or
the question is dropped before the entity check.

"The October 20 interview" was 14% of the entity check's rejects on DemoSyft
(demo-question-removal, 14.10 onwards), after the writer prompts had asked for
the year since 13.10.
"""

from __future__ import annotations

from datetime import date

import pytest

from syft_benchmark.generation import yearless
from syft_benchmark.generation.abstractive import TTIL_HEAD
from syft_benchmark.generation.extractive import FILL_IN_PREFIX
from syft_benchmark.generation.pair import Pair

PUBLISHED = date(2026, 11, 10)


def _pair(question: str, answer: str = "x", **meta: object) -> Pair:
    return Pair(question=question, answer=answer, distractors=[], meta=dict(meta))


@pytest.mark.parametrize(
    ("written", "repaired"),
    [
        (
            "What did Ana Pérez say in the October 20 interview?",
            "What did Ana Pérez say in the October 20, 2026 interview?",
        ),
        (
            "¿Qué anunció el Ministerio de Economía de Uruguay el 20 de octubre?",
            "¿Qué anunció el Ministerio de Economía de Uruguay el 20 de octubre de "
            "2026?",
        ),
        (
            "¿Cuántos votos obtuvo el Frente Amplio en octubre pasado?",
            "¿Cuántos votos obtuvo el Frente Amplio en octubre de 2026?",
        ),
        (
            "¿Qué ocurrió en Montevideo el pasado 3 de diciembre?",
            "¿Qué ocurrió en Montevideo el 3 de diciembre de 2025?",
        ),
        (
            "¿Cuándo empiezan las obras previstas para el próximo 5 de enero?",
            "¿Cuándo empiezan las obras previstas para el 5 de enero de 2027?",
        ),
        (
            "Quanto custou a obra inaugurada em 1º de maio?",
            "Quanto custou a obra inaugurada em 1º de maio de 2026?",
        ),
        (
            "Qu'a annoncé le ministre le 1er mars ?",
            "Qu'a annoncé le ministre le 1er mars 2026 ?",
        ),
        (
            "Was geschah am 3. Oktober in Berlin?",
            "Was geschah am 3. Oktober 2026 in Berlin?",
        ),
        ("What happened in March at Acme?", "What happened in March 2026 at Acme?"),
    ],
)
def test_a_date_gets_the_year_around_the_publish_date(
    written: str, repaired: str
) -> None:
    fixed = yearless.add_years(written, PUBLISHED)
    assert fixed.text == repaired
    assert fixed.repairs and not fixed.missing


def test_a_date_soon_after_the_story_is_next_year_and_a_far_one_last_year() -> None:
    soon = yearless.add_years("¿Qué se votará el 5 de enero?", PUBLISHED)
    far = yearless.add_years("¿Qué se votó el 5 de agosto?", PUBLISHED)
    assert soon.text.endswith("5 de enero de 2027?")
    assert far.text.endswith("5 de agosto de 2026?")


@pytest.mark.parametrize(
    "text",
    [
        "In the 2024 election held on October 27, who won Montevideo?",
        "¿Qué anunció el Ministerio el 20 de octubre de 2026?",
        "What did the board approve on October 20, 2026?",
        f"{FILL_IN_PREFIX} El 20 de octubre de ______ se firmó el acuerdo.",
        "How many people did Acme Corp employ in 2025?",
        "¿Cuántos mayoristas venden gasoil 50S en Uruguay?",
    ],
)
def test_a_text_with_a_year_or_without_a_date_is_left_alone(text: str) -> None:
    fixed = yearless.add_years(text, PUBLISHED)
    assert fixed.text == text and not fixed.repairs and not fixed.missing


def test_without_a_publish_date_the_question_is_dropped() -> None:
    kept, dropped = yearless.screen(
        "qa",
        [
            _pair("¿Qué anunció el Ministerio el 20 de octubre?"),
            _pair("¿Cuántos votos obtuvo el Frente Amplio en Montevideo en 2024?"),
        ],
        None,
    )
    assert [p.question for p in kept] == [
        "¿Cuántos votos obtuvo el Frente Amplio en Montevideo en 2024?"
    ]
    (drop,) = dropped
    assert drop.reason == yearless.NO_YEAR == "a date without its year"


def test_a_repair_is_recorded_on_the_pair() -> None:
    kept, dropped = yearless.screen(
        "qa", [_pair("¿Qué anunció el Ministerio el 20 de octubre?")], PUBLISHED
    )
    assert dropped == []
    assert kept[0].meta[yearless.META] == [
        {"from": "20 de octubre", "to": "20 de octubre de 2026"}
    ]


def test_a_choice_question_is_repaired_in_its_stem_only() -> None:
    question = (
        "¿Qué anunció Ana Pérez el 20 de octubre?\n  A) 20 de octubre\n"
        "  B) Un plan\n  C) Un recorte\n  D) Nada"
    )
    (kept,), _ = yearless.screen("mcq", [_pair(question, "B) Un plan")], PUBLISHED)
    stem, options = kept.question.split("\n", 1)
    assert stem == "¿Qué anunció Ana Pérez el 20 de octubre de 2026?"
    assert options.startswith("  A) 20 de octubre\n")


def test_two_truths_repairs_each_statement_in_every_field() -> None:
    lie = "El Ministerio de Economía de Uruguay subió el IVA el 20 de octubre."
    truth = "La Intendencia de Montevideo cerró la rambla en 2026."
    other = "El Frente Amplio ganó en Montevideo el 3 de noviembre."
    pair = Pair(
        question=f"{TTIL_HEAD}\n  A) {lie}\n  B) {truth}\n  C) {other}",
        answer=f"A) {lie}",
        distractors=[truth, other],
        meta={"claims": [truth, other], "source_detail": "subió el IVA"},
    )
    (kept,), _ = yearless.screen("two_truths_one_lie", [pair], PUBLISHED)
    fixed_lie = lie.replace("20 de octubre", "20 de octubre de 2026")
    fixed_other = other.replace("3 de noviembre", "3 de noviembre de 2026")
    assert kept.question.splitlines()[1:] == [
        f"  A) {fixed_lie}",
        f"  B) {truth}",
        f"  C) {fixed_other}",
    ]
    assert kept.answer == f"A) {fixed_lie}"
    assert kept.distractors == [truth, fixed_other]
    assert kept.meta["claims"] == [truth, fixed_other]


def test_an_explanation_is_repaired_in_its_topic() -> None:
    pair = _pair(
        "Explain this.\n\nTopic: the strike at ASSE on October 20",
        topic="the strike at ASSE on October 20",
    )
    (kept,), _ = yearless.screen("tiered_explanation", [pair], PUBLISHED)
    assert kept.meta["topic"] == "the strike at ASSE on October 20, 2026"
    assert kept.question.endswith("Topic: the strike at ASSE on October 20, 2026")
