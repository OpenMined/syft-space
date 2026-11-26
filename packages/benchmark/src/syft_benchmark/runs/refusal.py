"""Telling a refusal from an answer without a judge, in en, es, pt, fr, de.

The models answer in the question's language, so the phrases are matched in
every language at once: none of them is a phrase of another. A phrase is first
person or about the given context, never a bare "no information": an answer
reporting that an official "had no information" is still an answer. What
matches none of them goes to the judge, which grades a refusal it reads as
did not know: an unrecognised refusal costs a judge call, not a wrong verdict.

Only a whole-answer refusal skips the judge: every sentence says the model
does not know. A refusal phrase inside a longer answer ("... so I can't
confirm the author") or glued to the answer that follows it ("I don't
knowThe two obligations ...") goes to the judge.
"""

from __future__ import annotations

import re

_ABSTAIN_PATTERNS = (
    # en
    r"i don'?t (?:know|have (?:access|information|enough|the))",
    r"i'?m not (?:sure|certain|able|aware)",
    r"i (?:cannot|can'?t|am unable to) "
    r"(?:determine|answer|confirm|verify|find|provide)",
    r"(?:no|not enough) (?:information|context|data) (?:available|provided|in the)",
    r"the (?:provided )?context does not (?:contain|mention|provide|specify)",
    r"(?:is|are) not (?:mentioned|specified|provided) in the (?:context|document)",
    r"based on the (?:provided )?context,? i (?:cannot|can'?t|don'?t)",
    # es
    r"\bno (?:lo )?sé\b",
    r"\bno (?:tengo|dispongo de|cuento con|encuentro|encontré|he encontrado) "
    r"(?:\w+ )?(?:información|acceso|datos|registros?|suficiente)",
    r"\bno estoy (?:segur[oa]|en condiciones)",
    r"\bno (?:puedo|es posible) "
    r"(?:determinar|responder|confirmar|verificar|encontrar|proporcionar|precisar"
    r"|saber|indicar)",
    r"\b(?:el|los) (?:contexto|fragmentos?|documentos?) (?:proporcionados? )?"
    r"no (?:contienen?|mencionan?|incluyen?|especifican?|proporcionan?)",
    r"\bno se (?:menciona|especifica|indica|incluye) en (?:el|los) "
    r"(?:contexto|fragmentos?|documentos?)",
    # pt
    r"\bnão (?:sei|tenho (?:\w+ )?(?:informaç|acesso|dados))",
    r"\bnão estou (?:segur[oa]|cert[oa]|ciente)",
    r"\bnão (?:posso|consigo|é possível) "
    r"(?:determinar|responder|confirmar|verificar|encontrar|fornecer|precisar)",
    r"\bo contexto (?:fornecido )?não (?:contém|menciona|inclui|especifica)",
    # fr
    r"\bje ne (?:sais|connais) pas\b",
    r"\bje n'?ai pas (?:d'?informations?|accès|de données|assez)",
    r"\bje ne (?:peux|suis pas en mesure de) (?:pas )?"
    r"(?:déterminer|répondre|confirmer|vérifier|trouver|fournir|préciser)",
    r"\bje ne suis pas (?:sûr|certain)",
    r"\ble contexte (?:fourni )?ne (?:contient|mentionne|précise|fournit)",
    # de
    r"\bich weiß (?:es |das )?nicht\b",
    r"\bich habe keine (?:informationen|daten|kenntnis|angaben|zugang)",
    r"\bich kann (?:das |dies |es )?(?:nicht|keine \w+) "
    r"(?:bestimmen|beantworten|bestätigen|überprüfen|finden|sagen|angeben)",
    r"\bich bin (?:mir )?nicht sicher",
    r"\bder (?:bereitgestellte )?kontext enthält keine",
)
ABSTAIN_RE = re.compile("|".join(_ABSTAIN_PATTERNS), re.IGNORECASE)

# Signs that the model did give an answer after all, if with a hedge. A hedge
# plus an answer is a guess, not an abstention, and must be assessed as an answer.
ANSWER_SIGNALS_RE = re.compile(
    r"(?:^|\n)\s*[A-Da-d]\)|"
    r"[A-Da-d]\)\s+\w|"
    r"\b(?:the answer is|most likely|apparently)\b|"
    r"\b(?:la respuesta es|probablemente|aparentemente|al parecer)\b|"
    r"\b(?:a resposta é|provavelmente|aparentemente)\b|"
    r"\b(?:la réponse est|probablement|apparemment)\b|"
    r"\b(?:die antwort ist|wahrscheinlich|anscheinend)\b|"
    # The word boundaries here are mandatory: without them "though" is found
    # inside "Although", and an honest abstention is scored as an answer.
    r"\b(?:however|but|though|sin embargo|pero|aunque|no obstante|porém|mas|"
    r"embora|contudo|cependant|mais|toutefois|bien que|jedoch|aber|obwohl|"
    r"allerdings)\b[,;]?\s+\S+",
    re.IGNORECASE,
)

# A sentence that says the model does not know, cannot tell or lacks access.
NOT_KNOWING_RE = re.compile(
    r"\b(?:i|we)\s+(?:do not|don'?t|cannot|can'?t|am unable to|am not able to|"
    r"have no|lack)\b|"
    r"\bi'?m not (?:sure|certain|able|aware)\b|"
    r"\bwithout (?:access|information|details|data)\b|"
    r"\bno (?:information|details|data|access)\b|"
    r"\bno (?:sé|tengo|dispongo|cuento|puedo|encuentro|encontré)\b|"
    r"\bno estoy segur[oa]\b|"
    r"\bsin (?:acceso|información|datos)\b|"
    r"\bnão (?:sei|tenho|posso|consigo|estou)\b|"
    r"\bsem (?:acesso|informaç|dados)|"
    r"\bje (?:ne|n'?)\s*(?:sais|connais|peux|ai|suis)\b|"
    r"\bsans (?:accès|informations?|données)\b|"
    r"\bich (?:weiß|habe keine|kann (?:das |dies |es )?nicht|bin (?:mir )?nicht)|"
    r"\bohne (?:zugang|informationen|daten)\b",
    re.IGNORECASE,
)


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
# Markdown and list marks around a sentence, which say nothing.
_DECORATION = " \t*_#>-•"


def _glued(text: str) -> bool:
    """A refusal phrase run straight into more text: "I don't knowThe ...".

    Seen when a model writes "I don't know" before a web search and its answer
    after it: the provider joins the two turns' text with no separator.
    """
    for found in ABSTAIN_RE.finditer(text):
        after = text[found.end() : found.end() + 1]
        if after and (after.isupper() or after.isdigit() or after in "*#"):
            return True
    return False


def detect_abstain(answer: str) -> bool:
    """Whether the whole answer is a refusal: every sentence says the model
    does not know, nothing is glued to the refusal, and no answer signal."""
    text = (answer or "").strip()
    if not text:
        return True
    if not ABSTAIN_RE.search(text) or ANSWER_SIGNALS_RE.search(text):
        return False
    if _glued(text):
        return False
    sentences = [
        part.strip(_DECORATION)
        for part in _SENTENCE_RE.split(text)
        if part.strip(_DECORATION)
    ]
    return all(
        ABSTAIN_RE.search(sentence) or NOT_KNOWING_RE.search(sentence)
        for sentence in sentences
    )
