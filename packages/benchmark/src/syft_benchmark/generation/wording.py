"""Writer rules shared by every generator prompt.

The texts hold no braces: they go into prompts that are ``str.format``-ed.
"""

from __future__ import annotations

# Every prompt's user message opens with the document header
# (``generators.document_header``): title, outlet, author, publish date.
ANCHOR_RULE = (
    "Anchor time and authorship with the header above the text: turn a "
    'relative time into an absolute one counted from the publish date ("in '
    'the week to Oct 10, 2026", "in July 2026"; never "last month", "last '
    'week" or a month without its year); every date carries its year, even '
    'where the text leaves it out ("on Oct 20, 2026", "el 20 de octubre de '
    '2026"; never "on Oct 20" or "el 20 de octubre"); name the writer of a '
    "review, column, opinion or analysis piece or a "
    'first-person account as "<Outlet>\'s <Author>" ("WIRED\'s Nena '
    'Farrell"), or "<Outlet>" when the header names no author, never "the '
    'reviewer" or "the author"; never refer to the '
    "story by its title. Name a person by full name and role the first time, "
    'even where the story uses one name ("Indonesian President Prabowo '
    'Subianto", never "Prabowo"); spell out an abbreviation the first time '
    '("the General Elections Commission (KPU)"). An event the story announces '
    "for a date after its "
    "publish date had not happened when it was written: ask what was "
    'scheduled or planned ("was scheduled to start", "is planned for"), '
    'never how it went ("was played", "ended").'
)

# Fill-ins copy a sentence verbatim, so a relative time cannot be rewritten.
FILL_IN_TIME_RULE = (
    'Skip a sentence that places its fact only by a relative time ("last '
    'month", "on Tuesday", a date or a month without its year: "on Oct 20", '
    '"el 20 de octubre") or that speaks of '
    '"the reviewer" or "the author" without a name.'
)

# "According to the article" stays forbidden by the standalone rule; a claim's
# own source is not.
ATTRIBUTION_RULE = (
    "Keep a claim, estimate, accusation or opinion attributed to the person "
    "or body that makes it (\"according to Ana Pérez, Uruguay's minister of "
    'economy, ...", "según el Ministerio de Economía de Uruguay, ..."); never '
    "turn it into established fact. In a column, opinion or analysis piece "
    "the writer the header names makes its own claims (\"Tech Policy Press's "
    'Natalia Viana argued that ...").'
)

# Bylines and author bios are on the author's profile pages: the web answers
# them without the corpus.
NO_BYLINE_RULE = (
    "Never ask about the story's author, byline or signature, the writer's "
    "biography, or the outlet's staff, contact or subscription lines."
)

# The corpus is only worth measuring on what the outlet reported itself.
OWN_JOURNALISM_RULE = (
    "Use only the outlet's own reporting. Skip material it reproduces from "
    "others: wire copy (AFP, EFE, Reuters, AP, ANSA, DPA, Europa Press), a "
    "press release or statement reprinted as issued, another outlet's "
    'reporting it cites ("as reported by El País"), and general or historical '
    "background."
)

# A gold answer padded with background is judged against more than was asked.
TIGHT_ANSWER_RULE = (
    "The answer gives exactly what the question asks and nothing more: no "
    "background, no second fact, no explanation unless the question asks why."
)
