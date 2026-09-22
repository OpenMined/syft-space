"""An honesty benchmark for Syft Space endpoints.

Builds a "question — gold answer" dataset from a Space's corpus, tests models
and endpoints against it in two modes and hands the Space a verdict to publish.

There are no SyftHub credentials here and there must not be: metrics are put
out by the Space under its own account. See section 8 of the spec — the privacy
invariants.
"""

__version__ = "0.1.0"
