"""Preparing chunks: what makes a fit basis for a question and what does not."""

from syft_benchmark.sources import is_useful, strip_header


def test_header_is_separated_from_body() -> None:
    """The ETL puts its header at the start of the first chunk.

    As a source of questions it is useless, as a source of metadata quite the
    opposite, so it is cut off rather than thrown away.
    """
    raw = (
        "---\n"
        'title: "The SyftHub architecture"\n'
        'source: "docs"\n'
        'url: "https://example.org/a"\n'
        "\n"
        "The hub stores endpoint descriptions, but not the data itself."
    )
    body, header = strip_header(raw)

    assert header["title"] == "The SyftHub architecture"
    assert header["url"] == "https://example.org/a"
    assert body == "The hub stores endpoint descriptions, but not the data itself."


def test_unknown_keys_stay_in_the_body() -> None:
    """Ordinary text with a colon is not a header."""
    body, header = strip_header("Conclusion: the hub does not store documents.")
    assert header == {}
    assert body.startswith("Conclusion:")


def test_short_chunk_is_not_useful() -> None:
    assert not is_useful("Far too short.", min_chars=400)


def test_ordinary_text_passes() -> None:
    text = (
        "The hub stores endpoint descriptions and metadata about them, but not "
        "the documents themselves. "
    ) * 4 + "You can subscribe to updates in your profile settings."
    assert is_useful(text, min_chars=400)


def test_consent_banner_is_rejected() -> None:
    """Counting goes by all occurrences, not by the number of distinct markers.

    A consent banner repeats "cookie" a dozen times, whereas an ordinary
    paragraph mentions a subscription once and stays in work.
    """
    banner = (
        "We use cookie technology. Functional cookie files and analytics "
        "cookie files require your consent. See our privacy policy. "
    ) * 4
    assert not is_useful(banner, min_chars=100)
