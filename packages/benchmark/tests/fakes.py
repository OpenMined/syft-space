"""Stand-ins shared by the test modules: no Chroma, no provider, no database."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from syft_benchmark.config import PairStatus, Settings

OPENROUTER = "https://openrouter.ai/api/v1"


def openrouter_settings(**overrides: Any) -> Settings:
    """Settings with an external OpenRouter subject that the perimeter admits.

    One try per call (``max_consecutive_failures=0``), so a failing stub fails
    the call at once instead of being retried.
    """
    base: dict[str, Any] = {
        "subject_url": OPENROUTER,
        "subject_key": "sk-test",
        "allow_external_models": True,
        "external_hosts": ["openrouter.ai"],
        "max_consecutive_failures": 0,
    }
    return Settings(**{**base, **overrides})


class ChromaStub:
    """A Chroma client where every collection exists, under one id."""

    def __init__(self, *_: Any) -> None: ...

    def collection_id(self, _name: str) -> str:
        return "cid"


class JudgeRecorder:
    """A fake ``chat()``: one fixed reply, and every prompt it was sent."""

    def __init__(self, reply: str, meta: dict[str, Any] | None = None) -> None:
        self.reply = reply
        self.meta = meta or {}
        self.sent: list[tuple[str, str, dict[str, Any]]] = []

    def __call__(
        self, system: str, user: str, **kwargs: Any
    ) -> tuple[str, dict[str, Any]]:
        self.sent.append((system, user, kwargs))
        return self.reply, dict(self.meta)

    @property
    def prompts(self) -> list[tuple[str, str]]:
        return [(system, user) for system, user, _ in self.sent]


@dataclass
class FakePair:
    """A question-answer pair in the volume the code under test reads."""

    id: str = "pair-1"
    question: str = "What port does the rig use?"
    answer: str = "5442"
    context: str = "The port is published as 5442."
    task_type: str = "open"
    expected_behavior: str = "answer"
    generator: str = "cloze"
    doc_id: str = "doc-1"
    file_name: str = "setup.md"
    status: str = PairStatus.ACTIVE.value
    cohort: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def numbered(cls, number: int, **fields: Any) -> FakePair:
        """Pair ``number``: its own id and its own question."""
        return cls(
            id=f"pair-{number}",
            question=f"What port does rig {number} use?",
            **fields,
        )


class StoreStub:
    """A session stub: entered and called like ``session_scope``, it answers
    every query with ``rows`` and keeps the statements it was given."""

    def __init__(self, rows: list[Any] | None = None) -> None:
        self.rows = rows if rows is not None else []
        self.statements: list[Any] = []

    def __call__(self, *args: Any, **kwargs: Any) -> StoreStub:
        return self

    def __enter__(self) -> StoreStub:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False

    def execute(self, stmt: Any) -> StoreStub:
        self.statements.append(stmt)
        return self

    def all(self) -> list[Any]:
        return self.rows
