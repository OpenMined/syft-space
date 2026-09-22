"""Checking a target: can the benchmark reach the index, the node and the models.

The same thing the ``doctor`` command does, but for one target and in machine
form — so that the settings form can say "ChromaDB cannot be reached" at once,
rather than an hour into a run, in a log the owner does not read.

Three roads, and they are different. To the index the benchmark goes past the
Space API, over the internal network or through ``docker exec``; to the node, by
ordinary HTTP with a token; to the models, out through the perimeter to whatever
provider each role points at. Any one of them can work while another does not,
and merging them into a single "the target is reachable" flag would hide exactly
the part that is missing.

The models are the road most easily left broken. They are named in the
instrument, which is edited in a UI, while the address and key reaching them are
the installation's own layer — so an instrument full of a gateway's model names
on an installation with no gateway configured is a working configuration that
cannot answer a single question.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from syft_benchmark.config import (
    ARM_LETTER,
    ExternalCallBlocked,
    Settings,
    SpaceConfig,
    get_settings,
)
from syft_benchmark.llm import (
    LLMError,
    check_model_available,
    check_perimeter,
    configured_providers,
)
from syft_benchmark.runs.endpoint import endpoint_mode
from syft_benchmark.runs.execute import blocker_code
from syft_benchmark.sources import ChromaClient, ChromaError, load_documents


@dataclass(slots=True)
class Check:
    """What could be found out about a target without starting a measurement."""

    target: str
    corpus: bool = False
    transport: str = ""
    collection: str = ""
    # What is in the index at all. Needed for exactly the "wrong collection"
    # case: the owner is not obliged to know what the Space called the
    # collection after its dataset, and offering a choice is cheaper than
    # making them guess.
    available: list[str] = field(default_factory=list)
    chunks: int = 0
    usable: int = 0
    documents: int = 0
    endpoint: bool = False
    response_type: str = ""
    # An arm that is not measurable on this node, and why — as a code. Not a
    # settings error: on a retrieval node arm B does not exist by the design of
    # the product, and the owner should see this as a property of the node, not
    # as a breakage. A code, not a sentence: a foreign UI displays it, in its
    # own language.
    blocked_arms: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """A measurement of this target is possible in full."""
        return self.corpus and self.endpoint and not self.problems


def check(
    space: SpaceConfig, settings: Settings | None = None, *, collection: str = ""
) -> Check:
    """Walk both roads to the target and report what was found.

    Exceptions are not let out: an unreachable node is an answer to the check's
    question, not a failure of the check.
    """
    conf = settings or get_settings()
    out = Check(target=space.key)

    name = collection or space.collection or space.key
    try:
        client = ChromaClient(space, conf)
        collection_id = client.collection_id(name)
        # The transport is chosen at the very first call, not earlier: before
        # that the client does not yet know whether the index port is published.
        out.transport = client.transport or ""
        if collection_id is None:
            out.available = [str(c.get("name")) for c in client.collections()]
            out.problems.append(
                f"the index has no collection {name!r} "
                f"(available: {', '.join(out.available) or '—'})"
            )
        else:
            out.corpus = True
            out.collection = name
            out.chunks = client.count(collection_id)
            documents = load_documents(client, collection_id)
            out.documents = len(documents)
            out.usable = sum(len(d.chunks) for d in documents)
            if not out.usable:
                out.problems.append(
                    "there are no usable chunks — nothing to build questions from"
                )
    except ChromaError as exc:
        out.problems.append(f"the index is unreachable: {exc}")
    except Exception as exc:  # noqa: BLE001 - the owner needs the whole reason
        out.problems.append(f"index: {exc}")

    try:
        mode = endpoint_mode(space)
    except Exception as exc:  # noqa: BLE001 - the node may simply have been down
        out.problems.append(f"node: {exc}")
        mode = ""
    if mode:
        out.endpoint = True
        out.response_type = mode
        for arm in conf.arms:
            code = blocker_code(arm, mode, conf.context_source)
            if code:
                out.blocked_arms[ARM_LETTER.get(arm.value, arm.value)] = code
    elif not out.problems:
        out.problems.append("the node mode was not read — arm compatibility is unknown")

    # The perimeter, for the same reason as the index: it is one of the things
    # that will stop a measurement, and pressing "check" is a cheaper way to
    # find that out than an hour into a run.
    try:
        check_perimeter(conf)
    except ExternalCallBlocked as exc:
        out.problems.append(str(exc))
    else:
        # Only when the perimeter allows it: asking a blocked address would add
        # a timeout to a refusal already explained.
        out.problems.extend(_unreachable_models(conf))

    return out


def _unreachable_models(conf: Settings) -> list[str]:
    """Every configured model a role cannot actually get an answer from.

    One check per distinct address and name. On an external provider each is a
    one-token request — the only way to ask someone else's API whether it will
    accept a name, and far cheaper than the run it precedes.
    """
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for provider in configured_providers(conf):
        mark = (provider.url, provider.model)
        if mark in seen:
            continue
        seen.add(mark)
        try:
            check_model_available(provider=provider, settings=conf)
        except ExternalCallBlocked:
            # Already reported by the perimeter check, in its own words.
            continue
        except LLMError as exc:
            problems.append(f"{provider.role} {provider.model!r}: {exc}")
        except Exception as exc:  # noqa: BLE001 - the owner needs the whole reason
            problems.append(f"{provider.role} {provider.model!r}: {exc}")
    return problems
