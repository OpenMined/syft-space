"""Language detection by built-in function-word lists."""

from __future__ import annotations

import pytest

from syft_benchmark.generation.language import LANGUAGES, detect_language

# Realistic paragraphs: a news-like one and a technical one per language.
PARAGRAPHS: dict[str, list[str]] = {
    "en": [
        "The city council approved the new budget on Tuesday after a long debate "
        "about the cost of public transport. The mayor said that the plan would "
        "reduce delays and that most of the money will go to buses rather than "
        "new roads.",
        "The service stores endpoint metadata in a PostgreSQL database. When a "
        "request arrives, the router checks the token and forwards the query to "
        "the configured model, which returns an answer with the sources it used.",
    ],
    "ru": [
        "Городской совет во вторник утвердил новый бюджет после долгого спора о "
        "стоимости общественного транспорта. Мэр сказал, что план сократит "
        "задержки и что большая часть денег пойдёт на автобусы, а не на новые "
        "дороги.",
        "Сервис хранит метаданные эндпоинтов в базе данных PostgreSQL. Когда "
        "приходит запрос, маршрутизатор проверяет токен и передаёт его модели, "
        "которая возвращает ответ вместе с источниками, на которые она опиралась.",
    ],
    "de": [
        "Der Stadtrat hat am Dienstag nach einer langen Debatte über die Kosten "
        "des öffentlichen Nahverkehrs den neuen Haushalt beschlossen. Der "
        "Bürgermeister sagte, dass der Plan die Verspätungen verringern werde und "
        "das meiste Geld in Busse statt in neue Straßen fließe.",
        "Der Dienst speichert die Metadaten der Endpunkte in einer "
        "PostgreSQL-Datenbank. Wenn eine Anfrage eintrifft, prüft der Router das "
        "Token und leitet sie an das konfigurierte Modell weiter, das eine "
        "Antwort mit den verwendeten Quellen zurückgibt.",
    ],
    "fr": [
        "Le conseil municipal a approuvé mardi le nouveau budget après un long "
        "débat sur le coût des transports publics. Le maire a déclaré que le plan "
        "réduirait les retards et que la plupart de l'argent irait aux bus plutôt "
        "qu'à de nouvelles routes.",
        "Le service stocke les métadonnées des points d'accès dans une base de "
        "données PostgreSQL. Lorsqu'une requête arrive, le routeur vérifie le "
        "jeton et la transmet au modèle configuré, qui renvoie une réponse avec "
        "les sources utilisées.",
    ],
    "es": [
        "El ayuntamiento aprobó el martes el nuevo presupuesto tras un largo "
        "debate sobre el coste del transporte público. El alcalde dijo que el "
        "plan reducirá los retrasos y que la mayor parte del dinero irá a los "
        "autobuses y no a nuevas carreteras.",
        "El servicio guarda los metadatos de los puntos de acceso en una base de "
        "datos PostgreSQL. Cuando llega una solicitud, el enrutador comprueba el "
        "token y la envía al modelo configurado, que devuelve una respuesta con "
        "las fuentes que ha usado.",
    ],
    "it": [
        "Il consiglio comunale ha approvato martedì il nuovo bilancio dopo un "
        "lungo dibattito sul costo dei trasporti pubblici. Il sindaco ha detto "
        "che il piano ridurrà i ritardi e che la maggior parte dei soldi andrà "
        "agli autobus e non a nuove strade.",
        "Il servizio memorizza i metadati degli endpoint in un database "
        "PostgreSQL. Quando arriva una richiesta, il router controlla il token e "
        "la inoltra al modello configurato, che restituisce una risposta con le "
        "fonti che ha usato.",
    ],
    "pt": [
        "A câmara municipal aprovou na terça-feira o novo orçamento depois de um "
        "longo debate sobre o custo dos transportes públicos. O prefeito disse "
        "que o plano vai reduzir os atrasos e que a maior parte do dinheiro irá "
        "para os ônibus e não para novas estradas.",
        "O serviço guarda os metadados dos endpoints num banco de dados "
        "PostgreSQL. Quando chega um pedido, o roteador verifica o token e o "
        "encaminha para o modelo configurado, que devolve uma resposta com as "
        "fontes que usou.",
    ],
    "nl": [
        "De gemeenteraad heeft dinsdag na een lang debat over de kosten van het "
        "openbaar vervoer de nieuwe begroting goedgekeurd. De burgemeester zei "
        "dat het plan de vertragingen zal verminderen en dat het meeste geld naar "
        "bussen gaat en niet naar nieuwe wegen.",
        "De dienst slaat de metadata van de endpoints op in een "
        "PostgreSQL-database. Als er een verzoek binnenkomt, controleert de "
        "router het token en stuurt het door naar het geconfigureerde model, dat "
        "een antwoord geeft met de bronnen die het heeft gebruikt.",
    ],
}


# Item-sized texts, as the wrong-language check sees them: the English prefix
# the masking items carry, then the sentence.
QUESTIONS: dict[str, str] = {
    "en": "Fill in the blank: The mayor said that most of the money will go to "
    "______ rather than to new roads.",
    "ru": "Fill in the blank: Мэр сказал, что большая часть денег пойдёт на "
    "______, а не на новые дороги.",
    "de": "Fill in the blank: Der Bürgermeister sagte, dass das meiste Geld in "
    "______ statt in neue Straßen fließe.",
    "fr": "Fill in the blank: Le maire a déclaré que la plupart de l'argent irait "
    "aux ______ plutôt qu'à de nouvelles routes.",
    "es": "Fill in the blank: El alcalde dijo que la mayor parte del dinero irá "
    "a los ______ y no a nuevas carreteras.",
    "it": "Fill in the blank: Il sindaco ha detto che la maggior parte dei soldi "
    "andrà agli ______ e non a nuove strade.",
    "pt": "Fill in the blank: O prefeito disse que a maior parte do dinheiro irá "
    "para os ______ e não para novas estradas.",
    "nl": "Fill in the blank: De burgemeester zei dat het meeste geld naar ______ "
    "gaat en niet naar nieuwe wegen.",
}


def test_every_language_has_a_list() -> None:
    assert set(LANGUAGES) == set(PARAGRAPHS)


@pytest.mark.parametrize(
    ("lang", "text"),
    [(lang, text) for lang, texts in PARAGRAPHS.items() for text in texts],
)
def test_detects_each_language(lang: str, text: str) -> None:
    assert detect_language(text) == lang


@pytest.mark.parametrize(("lang", "text"), list(QUESTIONS.items()))
def test_detects_an_item_sized_text(lang: str, text: str) -> None:
    assert detect_language(text) == lang


def test_short_text_gives_no_verdict() -> None:
    assert detect_language("Hub stores") is None


def test_code_gives_no_verdict() -> None:
    code = (
        "def main(): config = load_config(path); args = parse_args(argv); "
        "return run(config, args, timeout=30, retries=5, verbose=True)"
    )
    assert detect_language(code) is None
