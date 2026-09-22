"""The local LLM: generating pairs and judging."""

from syft_benchmark.llm.ollama import (
    LLMError,
    LLMFatalError,
    LLMTruncatedError,
    chat,
    check_model_available,
    parse_json_list,
    parse_json_object,
)
from syft_benchmark.llm.roles import (
    JudgeConflict,
    Provider,
    check_judge_independence,
    check_perimeter,
    configured_providers,
    conflict_between,
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
    "conflict_between",
    "configured_providers",
    "generator_provider",
    "is_recused",
    "judge_provider",
    "judge_providers",
    "subject_providers",
    "vendor_of",
    "LLMError",
    "LLMFatalError",
    "LLMTruncatedError",
    "chat",
    "check_model_available",
    "parse_json_list",
    "parse_json_object",
]
