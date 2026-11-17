"""An honesty benchmark for Syft Space endpoints.

Builds a "question — gold answer" dataset from a Space's corpus, tests models
and endpoints against it in two modes. Results stay inside the Space.

There are no SyftHub credentials here and there must not be: see the privacy
invariants in docs/privacy.md.
"""

__version__ = "0.1.0"
