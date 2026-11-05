"""The writer calls of a job that threw drafts away or failed (``WriterCall``).

A call whose drafts all became pairs is on those pairs (``recorded``). One
that dropped any, or failed, is kept here as well: one row per call, with what
it dropped per kind and why, in the words of the kind's ``dropped`` counts.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy.dialects.postgresql import insert

from syft_benchmark.config import Settings
from syft_benchmark.db import WriterCall, session_scope
from syft_benchmark.generation.pair import Dropped
from syft_benchmark.generation.recorded import masked_user

# How much of a dropped draft's question and answer is kept.
MAX_DRAFT_CHARS = 2000


def digest(text: str) -> str:
    """The system prompt's fingerprint: its full text is kept once per build."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _draft(draft: Dropped) -> dict[str, str]:
    return {
        "question": draft.question[:MAX_DRAFT_CHARS],
        "answer": draft.answer[:MAX_DRAFT_CHARS],
        "reason": draft.reason,
    }


class WriterLog:
    """One build's writing log: the calls it keeps under its job.

    Used from the build's dispatching thread only. It remembers which system
    prompts it has stored, so a repeated prompt costs no query: the text is
    written on the first row that carries it and left empty on the rest.
    """

    def __init__(self, job: str, settings: Settings | None = None) -> None:
        self.job = job
        self.settings = settings
        self._stored: set[str] = set()

    def keep(
        self,
        call: Mapping[str, Any],
        dropped: Mapping[str, Sequence[Dropped]],
        *,
        document_title: str,
        file_name: str,
        passage: str,
        error: str | None = None,
    ) -> None:
        """Keep one call as one row; nothing without a job or a kind, and
        nothing for a call the job's log already holds (the first row wins).

        Args:
            call: The call (``recorded.new_call``); empty — it was not made
            dropped: Per kind, the drafts it dropped; for a failed call, every
                kind it was asked for, with none
            passage: The unit's text, when ``call`` has none
            error: Why the call failed; None — it did not
        """
        if not self.job or not dropped:
            return
        passage = str(call.get("passage") or passage)
        system = str(call.get("system") or "")
        signed = digest(system)
        first = bool(system) and signed not in self._stored
        try:
            with session_scope(self.settings) as session:
                stmt = (
                    insert(WriterCall)
                    .values(
                        id=uuid.uuid4().hex,
                        job_id=self.job,
                        call=str(call.get("call") or uuid.uuid4().hex),
                        model=str(call.get("model") or ""),
                        document_title=document_title,
                        file_name=file_name,
                        passage=passage,
                        system=system if first else "",
                        system_digest=signed,
                        user=masked_user(str(call.get("user") or ""), passage),
                        reply=str(call.get("reply") or ""),
                        cost_usd=call.get("cost_usd"),
                        latency_s=call.get("latency_s"),
                        error=error,
                        dropped={
                            kind: [_draft(draft) for draft in drafts]
                            for kind, drafts in dropped.items()
                        },
                        created_at=datetime.now(UTC),
                    )
                    .on_conflict_do_nothing(index_elements=["job_id", "call"])
                    .returning(WriterCall.id)
                )
                kept = session.execute(stmt).first() is not None
        except Exception:  # noqa: BLE001 - a lost record must not stop a paid build
            logger.exception(f"{self.job}: a writer call was not kept")
            return
        # A skipped duplicate stored no prompt text: the next row carries it.
        if first and kept:
            self._stored.add(signed)
