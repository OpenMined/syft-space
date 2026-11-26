"""The deterministic checks in any corpus language: grounding of the gold
answer, refusal detection and fill-in matching.

English behaves as before; Spanish, Portuguese, French and German get their own
function words, refusal phrases, articles, number words and dates. What is
not recognised still goes to the judge.
"""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.config import Settings, Verdict
from syft_benchmark.generation.validate import review_answer, review_claims
from syft_benchmark.llm import judge_provider
from syft_benchmark.runs import detect_abstain
from syft_benchmark.runs import judge as judge_module
from syft_benchmark.runs.fill_in import match_fill_in
from syft_benchmark.runs.judge import Gradable, bare_decline, grade_item

# --- grounding ------------------------------------------------------------------

CHUNK_ES = (
    "Según el informe, la mayoría de los vecinos de la ciudad de Montevideo dijo "
    "que en el barrio no hay luz desde que se fue el invierno y que la "
    "intendencia no responde a los reclamos de los comerciantes de la zona."
)
CHUNK_EN = (
    "The war in the region ended in 2024, and the city council said that the "
    "reconstruction of the bridge would cost 40 million dollars over five years."
)


def test_spanish_function_words_ground_nothing() -> None:
    """Every content word of the answer is missing; only "la", "de", "en", "el"
    are in the chunk. English stop words alone gave this 50% coverage."""
    answer = "La cifra de la inflación en el país del sur"
    assert not review_answer(answer, CHUNK_ES, Settings()).grounded
    assert review_answer(answer, CHUNK_ES, Settings(), language=None).coverage == 0.5


def test_a_spanish_answer_from_the_chunk_is_grounded() -> None:
    answer = "La intendencia de Montevideo no responde a los reclamos"
    review = review_answer(answer, CHUNK_ES, Settings())
    assert review.grounded and review.coverage == 1.0


def test_accents_do_not_split_a_word() -> None:
    chunk = CHUNK_ES + " El presidente Yamandú Orsi visitó Perú en octubre de 2026."
    assert review_answer("Yamandu Orsi visitó Peru", chunk, Settings()).grounded


def test_spanish_claims_are_checked_in_spanish() -> None:
    claims = ["La intendencia no responde a los reclamos", "La cifra de la inflación"]
    review = review_claims(claims, CHUNK_ES, Settings())
    assert review.coverage == 0.5 and not review.grounded


def test_english_keeps_its_content_words() -> None:
    """German "war" and "die" are function words only in a German text."""
    review = review_answer("The war ended in 2024", CHUNK_EN, Settings())
    assert review.grounded
    assert not review_answer("The war ended in 2025", CHUNK_EN, Settings()).grounded


# --- refusals --------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "No tengo información sobre ese anuncio.",
        "No tengo suficiente información para responder.",
        "No lo sé.",
        "No puedo determinar cuántos vecinos firmaron el reclamo.",
        "El contexto proporcionado no menciona esa cifra.",
        "No se menciona en los fragmentos.",
        "Não tenho informações sobre isso.",
        "Je ne sais pas.",
        "Le contexte fourni ne mentionne pas ce chiffre.",
        "Ich weiß es nicht.",
        "Ich habe keine Informationen dazu.",
        "I don't know.",
    ],
)
def test_refusals_in_each_language(answer: str) -> None:
    assert detect_abstain(answer)


@pytest.mark.parametrize(
    "answer",
    [
        # A hedge with an answer is an answer.
        "No estoy seguro, pero creo que fueron 30 pesos.",
        "No tengo información exacta; probablemente 30 pesos.",
        "Je ne suis pas sûr, mais je pense que c'était en mars.",
        "Ich bin mir nicht sicher, aber es waren wohl 30 Pesos.",
        # Reported ignorance is content, not a refusal.
        "El ministerio dijo que no hay información sobre los detenidos.",
        "El boleto cuesta 30 pesos.",
    ],
)
def test_answers_are_not_refusals(answer: str) -> None:
    assert not detect_abstain(answer)


def test_a_spanish_refusal_costs_no_judge_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    def fake_chat(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        calls.append(args)
        return '{"correct": false, "false_claims": false}', {}

    monkeypatch.setattr(judge_module, "chat", fake_chat)
    graded = grade_item(
        Gradable(
            question="¿Cuánto costará el plan de transporte al año?",
            expected="450 millones de pesos",
        ),
        "No tengo información sobre el costo del plan.",
        settings=Settings(),
        judge=judge_provider(Settings()),
    )
    assert graded.verdict is Verdict.ABSTAIN
    assert calls == []


def test_a_spanish_bare_decline_is_every_sentence_saying_so() -> None:
    assert bare_decline("No tengo información sobre ese plan. No puedo confirmarlo.")
    assert not bare_decline(
        "No tengo información sobre ese plan. El intendente es Mario Bergara."
    )


# --- fill-ins --------------------------------------------------------------------

ES = (
    "Fill in the blank: El Gobierno presentó el proyecto ante ______ el martes "
    "en la capital."
)
ES_NUMBER = (
    "Fill in the blank: La inflación interanual se ubicó en ______ en octubre, "
    "según el instituto."
)
ES_DATE = (
    "Fill in the blank: La ley entró en vigor el ______ tras su promulgación por "
    "el Poder Ejecutivo."
)
DE = (
    "Fill in the blank: Das Gesetz trat am ______ in Kraft, wie die Regierung "
    "mitteilte."
)
FR = (
    "Fill in the blank: Le projet a été présenté par ______ devant les députés à Paris."
)
EN = (
    "Fill in the blank: The company moved its headquarters to ______ in 2019, "
    "the filing shows."
)


@pytest.mark.parametrize(
    ("question", "expected", "answer"),
    [
        (ES, "el Parlamento", "Parlamento"),
        (ES, "el Parlamento", "La respuesta es: el Parlamento"),
        (ES, "José Mujica", "Jose Mujica"),
        (ES, "la Asamblea General", "Asamblea General."),
        (ES_NUMBER, "5,2%", "5,2 por ciento"),
        (ES_NUMBER, "1.500", "1500"),
        (ES_NUMBER, "dos", "2"),
        (ES_DATE, "1 de marzo de 2026", "1.º de marzo de 2026"),
        (ES_DATE, "15 de marzo de 2026", "March 15, 2026"),
        (ES_DATE, "marzo de 2026", "March 2026"),
        (DE, "15. März 2026", "15 März 2026"),
        (FR, "le Premier ministre", "Premier ministre"),
        (FR, "l'Élysée", "Elysée"),
    ],
)
def test_equivalent_spans_match_in_other_languages(
    question: str, expected: str, answer: str
) -> None:
    assert match_fill_in(question, expected, answer)


@pytest.mark.parametrize(
    ("question", "expected", "answer"),
    [
        (ES_NUMBER, "1,5", "15"),
        (ES_NUMBER, "1.500", "1.5"),
        (ES, "el Parlamento", "el Senado"),
        (ES_DATE, "1 de marzo de 2026", "marzo de 2026"),
        # An English sentence keeps the "Los" of a name.
        (EN, "Los Angeles", "Angeles"),
        (EN, "La Paz", "Paz"),
    ],
)
def test_other_spans_do_not_match(question: str, expected: str, answer: str) -> None:
    assert not match_fill_in(question, expected, answer)
