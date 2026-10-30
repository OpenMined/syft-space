"""Service routes about the installation itself: what it can do, the models a
form may offer, the settings form's shape and values, and sealed credentials."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import ValidationError

from syft_benchmark.config import (
    MEASURED_ARMS,
    EvalBlock,
    ExternalCallBlocked,
    Settings,
    TextMetric,
    check_model_host,
    url_is_inside,
)
from syft_benchmark.control.auth import Guard
from syft_benchmark.control.compose import effective_defaults
from syft_benchmark.control.formfields import catalogue
from syft_benchmark.control.schemas import (
    Capabilities,
    ModelCatalogView,
    ProviderInfo,
    RoleProvider,
    SecretValue,
    SecretView,
    SettingsChanges,
    csv_param,
)
from syft_benchmark.db import store
from syft_benchmark.db.crypto import SecretsNotConfigured
from syft_benchmark.db.store import SettingRejected
from syft_benchmark.generation import GENERATORS
from syft_benchmark.llm import catalog, judge_providers, subject_providers
from syft_benchmark.llm import openrouter as openrouter_catalogue
from syft_benchmark.llm.catalog import ModelEntry
from syft_benchmark.llm.client import installed_models
from syft_benchmark.llm.providers import ProviderKind, kind_for_url

router = APIRouter()


@router.get("/capabilities", response_model=Capabilities)
def capabilities(conf: Guard) -> Capabilities:
    """What this installation can do, so a form offers only what will run."""
    return Capabilities(
        version="1",
        profile=conf.methodology_profile,
        arms=[m.value for m in MEASURED_ARMS],
        blocks=[b.value for b in EvalBlock],
        # The registry's order, which is the reading order everywhere this
        # list is drawn: the control set, whose correct answer is a refusal,
        # comes last.
        generators=list(GENERATORS),
        subject_models=[p.model for p in subject_providers(conf)],
        judge_models=[p.model for p in judge_providers(conf)],
        text_metrics=[m.value for m in TextMetric],
        external_models=conf.allow_external_models,
        provider=provider_info(conf),
    )


@router.get("/models", response_model=ModelCatalogView)
def models(
    conf: Guard,
    q: str = "",
    vendor: str = "",
    supports: str = "",
    lacks: str = "",
    web_search: str = "",
    include_retired: bool = False,
    limit: int = 0,
) -> ModelCatalogView:
    """The models a form may offer, filtered as the picker asks.

    Filtered here so that what "supports temperature" means has one
    implementation.

    Args:
        q: Free text over the identifier and the shown name
        vendor: One vendor only
        supports: Comma-separated request parameters the model must honour
        lacks: Comma-separated request parameters the model must not take
        web_search: native, plugin, none, or any (native or plugin)
        include_retired: Keep models the provider has dated for withdrawal
        limit: Cap on the answer; zero — everything

    Raises:
        HTTPException: an unknown web_search value
    """
    needed = csv_param(supports)
    absent = csv_param(lacks)
    searching = web_search.strip().lower()
    if searching and searching not in (*catalog.WEB_SEARCH_VALUES, "any"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "web_search must be one of native, plugin, none, any",
        )
    catalogue_now = catalog.load(conf)
    found = catalogue_now.search(
        query=q,
        vendor=vendor,
        supports=needed,
        lacks=absent,
        web_search=searching,
        include_retired=include_retired,
    )
    # Asked live: the list is one request away and always right.
    local = [
        entry
        for entry in local_models(conf, query=q, vendor=vendor)
        if catalog.entry_matches(entry, needed, absent, searching)
    ]
    found = local + found
    return ModelCatalogView(
        models=found[:limit] if limit > 0 else found,
        vendors=catalogue_now.vendors(),
        pins=catalogue_now.pins,
        fetched=catalogue_now.fetched,
        total=len(found),
    )


@router.post("/models/refresh", response_model=ModelCatalogView)
def refresh_models(conf: Guard) -> ModelCatalogView:
    """Fetch the provider's model list afresh and store it.

    On request only: it is a call over the perimeter.

    Raises:
        HTTPException: the perimeter forbids it, or the provider did not answer
    """
    try:
        check_model_host(openrouter_catalogue.MODELS_URL, conf)
    except ExternalCallBlocked as blocked:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"{blocked}. The catalogue is public, but fetching it is still a "
            f"call outside: add the host to external_hosts, or keep the "
            f"snapshot that ships with the service",
        ) from blocked

    try:
        document = openrouter_catalogue.snapshot()
    except Exception as error:  # noqa: BLE001 — the provider's, not ours
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"the model list could not be fetched: {error}",
        ) from error

    fresh = catalog.replace(document, conf)
    logger.info(
        f"model catalogue refreshed: {len(document.get('models') or [])} models"
    )
    return ModelCatalogView(
        models=fresh.search(),
        vendors=fresh.vendors(),
        pins=fresh.pins,
        fetched=fresh.fetched,
        total=len(fresh.models),
    )


@router.get("/schema", summary="The shape of the settings fields")
def form_schema(conf: Guard) -> dict[str, Any]:
    """Names, types, bounds and groups — no labels: wording is the displayer's."""
    return catalogue()


@router.get("/defaults", summary="The installation's effective defaults")
def defaults(conf: Guard) -> dict[str, Any]:
    """What an unset setting resolves to, so a form shows the value in force."""
    return effective_defaults(conf)


@router.get("/settings", summary="What this installation has overridden")
def get_settings_doc(conf: Guard) -> dict[str, Any]:
    """Only the overrides; ``/defaults`` answers the effective values.

    "top-5 because nobody changed it" and "top-5 because somebody chose it"
    differ: only the second survives a change to the built-in default.
    """
    return {"values": store.read(conf)}


@router.patch("/settings", summary="Change some of this installation's overrides")
def patch_settings_doc(changes: SettingsChanges, conf: Guard) -> dict[str, Any]:
    """Merge the fields given into the overrides; ``null`` removes one.

    The values are checked by building the settings with them applied, so a
    bound only the model knows is refused here rather than when the schedule
    fires. Answers the whole document as stored afterwards.
    """
    try:
        return {"values": store.update(conf, changes.values)}
    except SettingRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, exc.errors(include_url=False)
        ) from exc


# Secrets go in and never come out: only whether one exists, and since when.


@router.get("/credentials", response_model=list[SecretView])
def list_secrets(conf: Guard) -> list[SecretView]:
    return [
        SecretView(name=item.name, updated_at=item.updated_at)
        for item in store.secrets(conf)
    ]


@router.put("/credentials/{name}", status_code=status.HTTP_204_NO_CONTENT)
def put_secret(name: str, body: SecretValue, conf: Guard) -> None:
    """Store one secret, sealed.

    With no master key configured this refuses rather than storing plain text.
    """
    if name in store.RESERVED_NAMES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{name!r} is read from the environment and is not stored here",
        )
    try:
        store.set_secret(conf, name, body.value)
    except SecretsNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.delete("/credentials/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_secret(name: str, conf: Guard) -> None:
    if not store.clear_secret(conf, name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"there is no secret called {name!r}"
        )


def local_models(conf: Settings, *, query: str, vendor: str) -> list[ModelEntry]:
    """The models this installation has pulled, as catalogue entries.

    A vendor filter excludes them all: a local model has no vendor. An
    unreachable Ollama is a warning and an empty list — the form must still
    open while the model host is down.
    """
    if vendor:
        return []
    if kind_for_url(conf.ollama_url) is not ProviderKind.OLLAMA:
        # A gateway has no such route; asking would cost a doomed request on
        # every draw of the form.
        return []
    try:
        names = installed_models(conf.ollama_url)
    except Exception as error:  # noqa: BLE001 — see the docstring
        logger.warning(f"the local model list could not be read: {error}")
        return []

    needle = query.strip().lower()
    return [
        ModelEntry(id=name, name=name, source="ollama", local=True)
        for name in sorted(names)
        if not needle or needle in name.lower()
    ]


def provider_info(conf: Settings) -> ProviderInfo:
    """The model provider per role, described without any key."""
    roles = [
        ("generator", conf.generator_url, conf.generator_key),
        ("subject", conf.subject_url, conf.subject_key),
        ("judge", conf.judge_url, conf.judge_key),
        (
            "filter",
            conf.filter_url or conf.subject_url,
            conf.filter_key or conf.subject_key,
        ),
    ]
    return ProviderInfo(
        url=conf.ollama_url,
        local=url_is_inside(conf.ollama_url),
        app_name=conf.llm_app_name,
        key_set=bool(conf.llm_api_key),
        external_hosts=list(conf.external_hosts),
        roles=[
            RoleProvider(
                role=role,
                url=url or conf.ollama_url,
                key_set=bool(key or conf.llm_api_key),
                own=bool(url or key),
                local=url_is_inside(url or conf.ollama_url),
            )
            for role, url, key in roles
        ],
    )
