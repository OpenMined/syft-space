"""The field catalogue a settings form is drawn from: groups and shapes, no prose."""

from __future__ import annotations


def test_every_setting_is_placed_in_a_group() -> None:
    """A field without a group lands in the wrong place, and only the eye notices.

    Forty fields in one column in declaration order means "similarity
    threshold" sitting between "panel of judges" and "freshness window".
    """
    from syft_benchmark.control.formfields import GROUPS, catalogue

    named = {f["name"] for f in catalogue()["instrument"]} | {
        f["name"] for f in catalogue()["probe"]
    }
    assert named <= set(GROUPS), f"without a group: {sorted(named - set(GROUPS))}"


def test_the_field_catalogue_carries_no_prose() -> None:
    """Labels belong to whoever displays them, and in their reader's language.

    A field description in one language arriving in a UI written in another is
    not a translation, it is a breakage.
    """
    from syft_benchmark.control.formfields import catalogue

    allowed = {
        "name",
        "type",
        "group",
        "choices",
        # The name of a list too long to inline, not a word to show anybody.
        "catalog",
        "item_type",
        # A value code a number field also takes ("default"), not prose.
        "special",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }
    fields = catalogue()["instrument"] + catalogue()["probe"]
    extra = {key for field in fields for key in field} - allowed
    assert not extra, f"more than intended travelled outwards: {sorted(extra)}"


def test_a_choice_field_says_what_the_choices_are() -> None:
    """Otherwise the form will offer the set mode as free text and accept a typo."""
    from syft_benchmark.control.formfields import catalogue

    by_name = {f["name"]: f for f in catalogue()["probe"]}
    assert by_name["dataset_mode"]["choices"] == ["incremental", "rolling", "rebuild"]
    assert by_name["similarity_threshold"]["maximum"] == 1.0


def test_a_list_of_choices_keeps_both_the_shape_and_the_choices() -> None:
    """The arms are a list drawn from an enum, and the form has to know both facts."""
    from syft_benchmark.control.formfields import catalogue

    arms = next(f for f in catalogue()["instrument"] if f["name"] == "arms")
    assert arms["type"] == "array"
    assert arms["item_type"] == "string"
    assert "closed_book" in arms["choices"]
