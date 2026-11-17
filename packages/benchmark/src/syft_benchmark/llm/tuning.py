"""A judge call's temperature and reasoning effort, and stepping either down
when the provider refuses it.

https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
"""

from __future__ import annotations

import threading
from typing import Any

from syft_benchmark.config import Settings
from syft_benchmark.llm import catalog
from syft_benchmark.llm.errors import LLMFatalError
from syft_benchmark.llm.providers import ProviderKind, kind_for_url

# A refused effort steps down: "none" and "minimal" to "low" (some models reason
# by force), any other to the model's own default ("").
_EFFORT_FALLBACK = {"none": "low", "minimal": "low"}
# (wire model, asked effort) -> the effort its refusals left; "" sends none.
_EFFORT_STEPPED: dict[tuple[str, str], str] = {}
# Wire models that refused a temperature.
_NO_TEMPERATURE: set[str] = set()
_TUNING_LOCK = threading.Lock()


def judge_tuning(model: str, base_url: str, conf: Settings) -> dict[str, Any]:
    """The temperature and ``reasoning`` a judge call carries; absent — not sent.

    Temperature goes only to a model the catalogue says takes one (unknown — it
    does). Reasoning goes only to OpenRouter, and only to a model the catalogue
    lists with ``reasoning`` (unknown — sent, a refusal steps it down).
    """
    entry = catalog.load(conf).get(model)
    wire = catalog.load(conf).native(model, kind_for_url(base_url))
    out: dict[str, Any] = {}
    with _TUNING_LOCK:
        no_temperature = wire in _NO_TEMPERATURE
        asked = conf.judge_reasoning_effort.value
        effort = _EFFORT_STEPPED.get((wire, asked), asked)
    if (
        conf.judge_temperature is not None
        and catalog.load(conf).takes_temperature(model)
        and not no_temperature
    ):
        out["temperature"] = conf.judge_temperature
    reasons = entry is None or (not entry.local and "reasoning" in entry.supports)
    if (
        effort not in ("", "default")
        and reasons
        and kind_for_url(base_url) is ProviderKind.OPENROUTER
    ):
        out["reasoning"] = {"effort": effort, "exclude": True}
    return out


def refuses_tuning(
    error: LLMFatalError, named: str, body: dict[str, Any], wire: str, asked: str
) -> bool:
    """A refusal of the judge's reasoning or temperature: step it down in ``body``."""
    text = str(error).replace(named, "").lower()
    reasoning = body.get("reasoning")
    if isinstance(reasoning, dict) and any(
        word in text for word in ("reasoning", "effort", "thinking")
    ):
        lower = _EFFORT_FALLBACK.get(str(reasoning.get("effort")), "")
        with _TUNING_LOCK:
            _EFFORT_STEPPED[(wire, asked)] = lower
        if lower:
            body["reasoning"] = {**reasoning, "effort": lower}
        else:
            body.pop("reasoning")
        return True
    if "temperature" in body and "temperature" in text:
        with _TUNING_LOCK:
            _NO_TEMPERATURE.add(wire)
        body.pop("temperature")
        return True
    return False
