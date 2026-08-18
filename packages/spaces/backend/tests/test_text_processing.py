"""Tests for text processing utility — word cloud NLP pipeline."""

from __future__ import annotations

from syft_space.components.analytics.text_processing import clean_text_for_wordcloud


class TestCleanTextForWordcloud:
    """clean_text_for_wordcloud NLP pipeline."""

    def test_empty_input(self):
        assert clean_text_for_wordcloud("") == ""
        assert clean_text_for_wordcloud("   ") == ""

    def test_basic_lemmatization(self):
        # "running" and "runs" should both lemmatize to "run"
        result = clean_text_for_wordcloud("running runs")
        tokens = result.split()
        assert len(set(tokens)) == 1
        assert tokens[0] == "run"

    def test_removes_urls(self):
        result = clean_text_for_wordcloud(
            "check https://example.com for machine learning data"
        )
        assert "https" not in result
        assert "example" not in result
        assert "com" not in result

    def test_removes_emails(self):
        result = clean_text_for_wordcloud("contact user@test.com about analysis")
        assert "user" not in result.split()
        assert "test" not in result.split()

    def test_removes_punctuation(self):
        result = clean_text_for_wordcloud("hello, world! this is... great!!!")
        assert "," not in result
        assert "!" not in result
        assert "." not in result

    def test_removes_standalone_numbers(self):
        result = clean_text_for_wordcloud("chapter 42 has 100 examples")
        assert "42" not in result.split()
        assert "100" not in result.split()

    def test_removes_stop_words(self):
        result = clean_text_for_wordcloud("the quick brown fox jumps over the lazy dog")
        tokens = result.split()
        for stop in ["the", "over"]:
            assert stop not in tokens

    def test_custom_stop_words(self):
        result = clean_text_for_wordcloud(
            "machine learning endpoint dataset query",
            custom_stop_words=["endpoint", "dataset", "query"],
        )
        tokens = result.split()
        assert "endpoint" not in tokens
        assert "dataset" not in tokens
        assert "query" not in tokens

    def test_custom_stop_words_case_insensitive(self):
        result = clean_text_for_wordcloud(
            "Machine Learning Endpoint",
            custom_stop_words=["ENDPOINT"],
        )
        tokens = result.split()
        assert "endpoint" not in tokens

    def test_lowercase_normalization(self):
        result = clean_text_for_wordcloud("Machine LEARNING Natural Language")
        tokens = result.split()
        for token in tokens:
            assert token == token.lower()

    def test_min_token_length(self):
        result = clean_text_for_wordcloud("a I am an ox at", min_token_length=3)
        tokens = result.split()
        for token in tokens:
            assert len(token) >= 3

    def test_returns_space_separated_string(self):
        result = clean_text_for_wordcloud("artificial intelligence research papers")
        assert isinstance(result, str)
        # No double spaces
        assert "  " not in result

    def test_realistic_query(self):
        result = clean_text_for_wordcloud(
            "What are the latest developments in natural language processing "
            "and how do transformer models compare to recurrent neural networks?"
        )
        tokens = result.split()
        assert len(tokens) > 0
        # Should not contain question words / stop words
        for stop in ["what", "are", "the", "in", "and", "how", "do", "to"]:
            assert stop not in tokens
