"""Tests for `_extract_user_query` — analytics text extraction.

These guard the rule that only the user's actual question reaches the
analytics layer. System prompts and assistant turns must never pollute
the word cloud.
"""

from __future__ import annotations

from syft_space.components.endpoints.query_handler import _extract_user_query
from syft_space.components.endpoints.schemas import ChatMessageRequest


class TestExtractUserQuery:
    def test_string_messages_returned_as_is(self):
        assert _extract_user_query("how do I deploy?") == "how do I deploy?"

    def test_string_messages_are_stripped(self):
        assert _extract_user_query("  hello  ") == "hello"

    def test_empty_string(self):
        assert _extract_user_query("") == ""

    def test_empty_list(self):
        assert _extract_user_query([]) == ""

    def test_single_user_message(self):
        msgs = [ChatMessageRequest(role="user", content="what is X?")]
        assert _extract_user_query(msgs) == "what is X?"

    def test_system_prompt_is_excluded(self):
        msgs = [
            ChatMessageRequest(role="system", content="You are a helpful assistant."),
            ChatMessageRequest(role="user", content="what is X?"),
        ]
        assert _extract_user_query(msgs) == "what is X?"

    def test_assistant_turn_is_excluded(self):
        msgs = [
            ChatMessageRequest(role="user", content="hi"),
            ChatMessageRequest(role="assistant", content="hello, how can I help?"),
            ChatMessageRequest(role="user", content="what is X?"),
        ]
        assert _extract_user_query(msgs) == "what is X?"

    def test_multiple_user_turns_returns_last_only(self):
        msgs = [
            ChatMessageRequest(role="user", content="first question"),
            ChatMessageRequest(role="assistant", content="some answer"),
            ChatMessageRequest(role="user", content="latest question"),
        ]
        # Earlier turns were captured as their own events; only the
        # current turn should contribute to *this* event's analytics.
        assert _extract_user_query(msgs) == "latest question"

    def test_only_system_messages_returns_empty(self):
        msgs = [
            ChatMessageRequest(role="system", content="You are a bot."),
            ChatMessageRequest(role="assistant", content="Hello!"),
        ]
        assert _extract_user_query(msgs) == ""

    def test_unknown_role_is_dropped(self):
        msgs = [
            ChatMessageRequest(role="tool", content="some tool output"),
            ChatMessageRequest(role="function", content="some function result"),
        ]
        assert _extract_user_query(msgs) == ""

    def test_empty_user_content_falls_back_to_earlier_user_turn(self):
        # If the latest user turn has empty content, scan further back
        # rather than returning empty (e.g., a malformed client send).
        msgs = [
            ChatMessageRequest(role="user", content="real question"),
            ChatMessageRequest(role="assistant", content="answer"),
            ChatMessageRequest(role="user", content=""),
        ]
        assert _extract_user_query(msgs) == "real question"

    def test_user_content_is_stripped(self):
        msgs = [ChatMessageRequest(role="user", content="  padded query  ")]
        assert _extract_user_query(msgs) == "padded query"

    # ---------- aggregator-wrapper unwrapping ----------
    # SyftHub's aggregator pre-bakes prompt-builder text into the user-role
    # message before forwarding to the Space. These cases mirror the four
    # templates in
    # syfthub/components/aggregator/.../prompt_builder.py.

    def test_no_context_template_unwrapped(self):
        wrapped = (
            "No data sources are configured for this query. "
            "Answer the question using your general knowledge as a helpful AI assistant.\n"
            "\n"
            "If the user expected document-grounded answers, they should "
            "configure data sources for their query.\n"
            "\n---\n"
            "USER QUESTION:\n"
            "Give me an essay about existentialism\n"
            "---"
        )
        msgs = [ChatMessageRequest(role="user", content=wrapped)]
        assert (
            _extract_user_query(msgs) == "Give me an essay about existentialism"
        )

    def test_empty_context_template_unwrapped(self):
        wrapped = (
            "The configured data sources did not return any documents for this query.\n"
            "\nIf the question requires specific information ...\n"
            "\n---\nUSER QUESTION:\nWhat does the spec say?\n---"
        )
        msgs = [ChatMessageRequest(role="user", content=wrapped)]
        assert _extract_user_query(msgs) == "What does the spec say?"

    def test_default_user_instructions_template_unwrapped(self):
        wrapped = (
            "Your goal is to answer the user's question using information from the provided documents...\n"
            "DOCUMENT FORMAT: ...\n"
            "HOW TO ANSWER: ...\n"
            "\n<documents>\n<document index=\"1\"><source>x/y</source>...</document>\n</documents>\n"
            "\n---\nUSER QUESTION:\nHow do I deploy?\n---"
        )
        msgs = [ChatMessageRequest(role="user", content=wrapped)]
        assert _extract_user_query(msgs) == "How do I deploy?"

    def test_citation_template_unwrapped(self):
        wrapped = (
            "Answer the user's question using the numbered sources below. "
            "Write in clear prose.\n"
            "At the end of each sentence ... [cite:N]\n"
            "SOURCES:\n[1]: doc one\n[2]: doc two\n"
            "\n---\nUSER QUESTION:\nWhich approach is better?\n---"
        )
        msgs = [ChatMessageRequest(role="user", content=wrapped)]
        assert _extract_user_query(msgs) == "Which approach is better?"

    def test_string_messages_with_wrapper_also_unwrapped(self):
        # Defense-in-depth: same logic on string-typed messages.
        wrapped = (
            "Some preamble.\n---\nUSER QUESTION:\nactual q\n---"
        )
        assert _extract_user_query(wrapped) == "actual q"

    def test_question_without_wrapper_passes_through(self):
        # Direct API calls don't have the wrapper; content is captured
        # verbatim.
        msgs = [ChatMessageRequest(role="user", content="just a plain query")]
        assert _extract_user_query(msgs) == "just a plain query"
