"""Calling models: the chat client, the roles, the catalogue and the cost meter."""

from syft_benchmark.llm.client import chat, check_model_available
from syft_benchmark.llm.errors import LLMError, LLMFatalError
from syft_benchmark.llm.json_reply import parse_json_list, parse_json_object
from syft_benchmark.llm.roles import (
    JudgeConflict,
    Provider,
    check_judge_independence,
    check_perimeter,
    configured_providers,
    generator_provider,
    is_recused,
    judge_provider,
    judge_providers,
    subject_providers,
    vendor_of,
)

__all__ = [
    "JudgeConflict",
    "Provider",
    "check_judge_independence",
    "check_perimeter",
    "configured_providers",
    "generator_provider",
    "is_recused",
    "judge_provider",
    "judge_providers",
    "subject_providers",
    "vendor_of",
    "LLMError",
    "LLMFatalError",
    "chat",
    "check_model_available",
    "parse_json_list",
    "parse_json_object",
]
