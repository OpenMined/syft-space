"""Model roles: generator, model under test, judge.

Three roles with separate providers. The separation is substantive, not formal:

  * the **generator** works over documents and therefore should normally stay
    inside the perimeter;
  * the **models under test** do not see documents at all — all they get is the
    question — and they are almost always external models: the point of the
    measurement is to compare the endpoint with what is available to everyone;
  * the **judge** must not be from the same provider as the model under test. A
    model more readily approves an answer in its own style, and a match of
    providers makes the verdict an interested one.

An empty address for a role means "take the shared one", from ollama_url. That
way a configuration with a single local model stays one line long, and the roles
can be pulled apart when that is actually needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from syft_benchmark.config import JudgePolicy, Settings, check_model_host
from syft_benchmark.llm import catalog
from syft_benchmark.llm.providers import ProviderKind, kind_for_url


@dataclass(frozen=True, slots=True)
class Provider:
    """Where to call, and with what key, for one role."""

    role: str
    url: str
    api_key: str
    model: str

    @property
    def vendor(self) -> str:
        """The model provider. Empty — it is local, there is no provider."""
        return vendor_of(self.model)

    @property
    def company(self) -> str:
        """Who made the model, with a vendor's several prefixes folded into one."""
        return company_of(self.model)

    @property
    def kind(self) -> ProviderKind:
        """Whose API answers at this address, and therefore how it names models."""
        return kind_for_url(self.url)

    @property
    def wire_model(self) -> str:
        """The model under the name this provider knows it by.

        What actually goes into the request, so that anything reporting on a
        role can say what was sent and not only what was asked for.
        """
        return catalog.load().native(self.model, self.kind)

    @property
    def build(self) -> str:
        """The dated build the catalogue says stands behind this name today.

        Empty for a local model, or one published since the last refresh: a
        guess would be indistinguishable from a fact in the run it is written
        into.
        """
        entry = catalog.load().get(self.model)
        return entry.build if entry is not None else ""

    @property
    def is_external(self) -> bool:
        return bool(self.api_key)


def vendor_of(model: str) -> str:
    """The provider, from the catalogue, falling back to the namespace.

    The namespace is the convention every gateway follows, so a model published
    since this installation's snapshot is still attributed rather than left
    without a vendor — and ``conflict_between`` reads no vendor as nothing to
    compare.
    """
    return catalog.load().vendor_of(model)


# A company that publishes under more than one prefix. The frontend mirrors this
# map for its own same-company check.
COMPANY_ALIASES: dict[str, str] = {
    "x-ai": "xai",
    "meta-llama": "meta",
    "mistralai": "mistral",
    "gemini": "google",
    "bytedance-seed": "bytedance",
}


def company_of(model: str) -> str:
    """The company behind a model: its vendor, through the alias map.

    Empty for a local model, which has no vendor.
    """
    vendor = vendor_of(model)
    return COMPANY_ALIASES.get(vendor, vendor)


# The roles that may search the web, and the toggle each one reads. The web
# check model always searches.
WEB_SEARCH_TOGGLES: dict[str, str | None] = {
    "closed_book": "web_search_closed_book",
    "with_context": "web_search_with_context",
    "generator": "web_search_generator",
    "judge": "web_search_judge",
    "filter": None,
}


def web_search_for(settings: Settings, role: str, model: str) -> tuple[bool, str]:
    """Whether this role's call searches the web, and with which engine.

    Args:
        settings: The effective settings
        role: closed_book, with_context, generator, judge or filter
        model: The model making the call

    Returns:
        (enabled, engine): engine is "native" or "plugin" (Exa), "" when off. "auto"
        takes native when the catalogue says the model has it; "native" asked of
        a model without it falls back to Exa, so the model still searches.
        A model the catalogue cannot search with (local) never searches.

    Raises:
        KeyError: an unknown role
    """
    toggle = WEB_SEARCH_TOGGLES[role]
    if toggle is not None and not getattr(settings, toggle):
        return False, ""
    capability = catalog.load(settings).web_search_of(model)
    if capability == "none":
        return False, ""
    wanted = str(settings.web_search_engine)
    if wanted == "plugin" or capability != "native":
        return True, "plugin"
    return True, "native"


def _resolve(role: str, url: str, key: str, model: str, settings: Settings) -> Provider:
    """Where this role is configured to call. No policy is applied here.

    The perimeter is not checked here: working out where a role points is also
    how ``/defaults`` and ``/capabilities`` describe the configuration, and a
    settings page must open whatever address is in it. Egress is guarded where
    egress happens — in the client, before every call — and the configuration
    by ``check_perimeter``.
    """
    return Provider(
        role=role,
        url=url or settings.ollama_url,
        api_key=key or settings.llm_api_key,
        model=model,
    )


def configured_providers(settings: Settings) -> list[Provider]:
    """Every role as it is configured, without judging any of them."""
    web_check = filter_provider(settings)
    return [
        generator_provider(settings),
        *subject_providers(settings),
        *judge_providers(settings),
        *([web_check] if web_check is not None else []),
    ]


def check_perimeter(settings: Settings) -> None:
    """Refuse a configuration that would call outside the perimeter.

    Called where work is about to begin, not where settings are read: this is
    the early warning, so that a misconfigured judge is found at the start of a
    measurement rather than in its third hour. The enforcement that cannot be
    bypassed is in the client, before each call.

    Raises:
        ExternalCallBlocked: a role points outside and permission is not given
    """
    for provider in configured_providers(settings):
        check_model_host(provider.url, settings)


def generator_provider(settings: Settings) -> Provider:
    """The provider for the item generator."""
    return _resolve(
        "generator",
        settings.generator_url,
        settings.generator_key,
        settings.generator_model,
        settings,
    )


def filter_provider(settings: Settings) -> Provider | None:
    """The web check model, at the subjects' provider. None — no web check."""
    if not settings.filter_model:
        return None
    return _resolve(
        "filter",
        settings.subject_url,
        settings.subject_key,
        settings.filter_model,
        settings,
    )


def judge_provider(settings: Settings) -> Provider:
    """The first judge of the panel.

    It is also the only one when no panel is configured. The blocks that make no
    sense to run once per judge (denial_loop, monte_carlo — they are expensive
    and measure the answerer behaviour, not the spread of assessments) take it.
    """
    return judge_providers(settings)[0]


def judge_providers(settings: Settings) -> list[Provider]:
    """The panel of judges.

    Each judge independently assesses the same answers: the divergence between
    them is the measure of how far the assessment can be trusted at all. An empty
    list in the settings means a single judge — ``judge_model``.
    """
    models = settings.judge_models or [settings.judge_model]
    # We keep the order and drop the duplicates: two identical judges would give
    # two identical assessments and double the bill, measuring nothing.
    unique = list(dict.fromkeys(models))
    return [
        _resolve("judge", settings.judge_url, settings.judge_key, model, settings)
        for model in unique
    ]


def subject_providers(settings: Settings) -> list[Provider]:
    """The models under test.

    An empty list in the settings means "test the generator model": that is a
    working case for a rig that never calls outside at all.
    """
    models = settings.subject_models or [settings.generator_model]
    return [
        _resolve("subject", settings.subject_url, settings.subject_key, model, settings)
        for model in models
    ]


class JudgeConflict(RuntimeError):
    """The judge and the model under test share a provider under a strict policy."""


def conflict_between(judge: Provider, subject: Provider) -> str | None:
    """A description of the conflict of interest, or None if there is none.

    A conflict is a match of providers; the special case of a model judging
    itself is covered by the same rule, and local models have no provider at all,
    in which case the names are compared.
    """
    if judge.company and judge.company == subject.company:
        return (
            f"the judge and the model under test are from one provider "
            f"({judge.company}): the verdict is an interested one"
        )
    if not judge.vendor and not subject.vendor and judge.model == subject.model:
        return f"the model {judge.model!r} judges itself"
    return None


def judge_clashes(settings: Settings) -> list[str]:
    """Every judge paired with a tested model from the same company, as sentences.

    Judged on the effective settings: the panel and the models under test the
    run would actually use. A local model clashes only with itself.
    """
    out: list[str] = []
    for judge in judge_providers(settings):
        for subject in subject_providers(settings):
            if conflict_between(judge, subject) is not None:
                out.append(
                    f"Judge {judge.model} and tested model {subject.model} "
                    f"are from the same company"
                )
    return out


def clash_refusal(settings: Settings) -> str | None:
    """Why a configuration may not be saved or launched, or None.

    Only under ``strict``. Under ``warn`` a clash is allowed and logged.
    """
    clashes = judge_clashes(settings)
    if not clashes:
        return None
    if settings.judge_policy is JudgePolicy.STRICT:
        return (
            "; ".join(clashes)
            + ". Pick a judge from another company, or remove the model from the test."
        )
    if settings.judge_policy is JudgePolicy.WARN:
        for line in clashes:
            logger.warning(line)
    return None


def check_judge_independence(
    judge: Provider, subject: Provider, settings: Settings
) -> str | None:
    """Check that the judge has no interest in the model under test.

    Args:
        judge: The judge provider
        subject: The model under test
        settings: The settings — the policy comes from them

    Returns:
        The warning text, or None if all is well

    Raises:
        JudgeConflict: the policy is strict and the providers matched
    """
    if settings.judge_policy is JudgePolicy.OFF:
        return None

    message = conflict_between(judge, subject)
    if message is None:
        return None

    if settings.judge_policy is JudgePolicy.STRICT:
        raise JudgeConflict(message)
    logger.warning(message)
    return message


def is_recused(judge: Provider, subject: Provider, settings: Settings) -> bool:
    """Whether this judge must abstain from assessing this model.

    A recusal is not the same as refusing the run: the disputed answers are
    simply left without this judge assessment, while the other judges carry on
    working. That is how a panel survives a match of providers — the very thing
    it is set up for.
    """
    if settings.judge_policy is not JudgePolicy.RECUSE:
        return False
    return conflict_between(judge, subject) is not None
