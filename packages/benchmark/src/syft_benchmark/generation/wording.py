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
    'week" or a month without its year); name the writer of a review or a '
    'first-person account as "<Outlet>\'s <Author>" ("WIRED\'s Nena '
    'Farrell"), never "the reviewer" or "the author"; never refer to the '
    "story by its title."
)

# Fill-ins copy a sentence verbatim, so a relative time cannot be rewritten.
FILL_IN_TIME_RULE = (
    'Skip a sentence that places its fact only by a relative time ("last '
    'month", "on Tuesday", a month without its year) or that speaks of '
    '"the reviewer" or "the author" without a name.'
)
