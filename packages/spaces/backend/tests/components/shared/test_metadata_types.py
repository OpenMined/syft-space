"""``DatasetMetadata``: the one filter every binding applies to a document's
metadata before it leaves the space."""

from __future__ import annotations

from syft_space.components.shared.metadata_types import (
    DatasetMetadata,
    MetadataField,
    MetadataFields,
)

META = {"title": "t", "author": "a", "prev_context": "…", "absolute_path": "/x"}


class _Source(MetadataFields):
    fields = (MetadataField(name="title"), MetadataField(name="author"))


class _Store(MetadataFields):
    fields = (MetadataField(name="prev_context", hidden=True),)

    def derived(self, source):
        return tuple(MetadataField(name=f"{f.name}_ts") for f in source.declared())


def test_composes_declared_and_derived_from_both_halves():
    dm = DatasetMetadata(_Source(), _Store())
    assert {f.name for f in dm.fields} == {
        "title",
        "author",
        "prev_context",
        "title_ts",
        "author_ts",
    }


def test_keeps_declared_public_keys_only():
    assert DatasetMetadata(_Source(), _Store()).public(META) == {
        "title": "t",
        "author": "a",
    }


def test_hidden_wins_when_a_key_is_declared_twice():
    class _Twice(MetadataFields):
        fields = (MetadataField(name="k"), MetadataField(name="k", hidden=True))

    assert DatasetMetadata(_Twice(), MetadataFields()).public({"k": 1}) == {}


def test_declared_but_absent_keys_are_not_invented():
    assert DatasetMetadata(_Source(), _Store()).public({}) == {}


def test_base_declaration_declares_and_derives_nothing():
    base = MetadataFields({"any": "config"})
    assert base.declared() == ()
    assert base.derived(base) == ()
    assert DatasetMetadata(base, base).public(META) == {}
