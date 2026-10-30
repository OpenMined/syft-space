"""Editable dataset configuration: axis flags, composed schema, split, redaction.

Each axis declares its own editable / secret fields on its config model;
the binding composes the flat schema, tags every property with its axis,
and reads the flags back. Nothing here touches the network.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from syft_space.components.dataset_types import register_builtin_types
from syft_space.components.dataset_types.interfaces import (
    BaseDatasetType,
    compose_schema,
)
from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.shared.config_flags import (
    Visibility,
    cfg_flags,
    editable_fields,
    fields_with_visibility,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator


@pytest.fixture(scope="module")
def registry() -> DatasetTypeRegistry:
    registry = DatasetTypeRegistry()
    register_builtin_types(registry)
    return registry


# ── cfg_flags ────────────────────────────────────────────────────────────


class TestCfgFlags:
    def test_unflagged_prints_nothing(self):
        assert cfg_flags() == {}

    def test_only_non_default_flags_are_written(self):
        assert cfg_flags(editable=True) == {"editable": True}
        assert cfg_flags(visibility=Visibility.SECRET) == {"visibility": "secret"}
        assert cfg_flags(visibility=Visibility.INTERNAL) == {"visibility": "internal"}
        assert cfg_flags(editable=False, visibility=Visibility.PUBLIC) == {}

    def test_the_printed_value_is_a_plain_string(self):
        assert type(cfg_flags(visibility=Visibility.SECRET)["visibility"]) is str

    def test_an_internal_field_cannot_be_editable(self):
        with pytest.raises(ValueError, match="internal"):
            cfg_flags(editable=True, visibility=Visibility.INTERNAL)

    def test_extras_pass_through(self):
        flags = cfg_flags(
            editable=True, visibility=Visibility.SECRET, format="password", enum=[1]
        )
        assert flags == {
            "format": "password",
            "enum": [1],
            "editable": True,
            "visibility": "secret",
        }

    def test_flags_reach_the_json_schema_under_the_alias(self):
        class Cfg(BaseModel):
            token: str = Field(
                ...,
                alias="apiToken",
                json_schema_extra=cfg_flags(visibility=Visibility.SECRET),
            )
            name: str = Field(...)

        schema = Cfg.model_json_schema(schema_generator=ConfigSchemaGenerator)
        assert fields_with_visibility(schema, Visibility.SECRET) == ["apiToken"]
        assert fields_with_visibility(schema, Visibility.INTERNAL) == []
        assert editable_fields(schema) == []


# ── compose_schema ───────────────────────────────────────────────────────


class TestComposeSchema:
    def test_tags_each_property_with_its_axis(self):
        composed = compose_schema(
            {"properties": {"a": {"type": "string"}}, "required": ["a"]},
            {"properties": {"b": {"type": "integer"}}, "required": ["b"]},
        )
        assert composed["properties"]["a"]["axis"] == "source"
        assert composed["properties"]["b"]["axis"] == "vector_store"
        assert composed["required"] == ["a", "b"]
        assert "$defs" not in composed

    def test_merges_defs_and_tolerates_a_bare_axis(self):
        composed = compose_schema(
            {"type": "object", "properties": {}},
            {"properties": {"f": {"$ref": "#/$defs/F"}}, "$defs": {"F": {}}},
        )
        assert composed["$defs"] == {"F": {}}
        assert composed["required"] == []

    def test_a_key_on_both_axes_is_a_programming_error(self):
        with pytest.raises(ValueError, match="both axes"):
            compose_schema({"properties": {"k": {}}}, {"properties": {"k": {}}})


# ── Built-in bindings ────────────────────────────────────────────────────

EXPECTED = {
    # name: (editable, secret, internal, locked public)
    "rss": (
        ["feedUrls", "pollIntervalSeconds"],
        [],
        ["httpPort"],
        ["collectionName"],
    ),
    "wordpress": (
        ["siteUrl", "username", "applicationPassword", "pollIntervalSeconds"],
        ["applicationPassword"],
        ["httpPort"],
        ["userAgent", "collectionName"],
    ),
    "blogspot": (
        ["blogUrls", "apiKey", "pollIntervalSeconds"],
        ["apiKey"],
        ["httpPort"],
        ["collectionName"],
    ),
    "local_file": (
        [],
        [],
        ["showHidden", "httpPort"],
        ["ingestFileTypeOptions", "collectionName"],
    ),
    "remote_weaviate": (
        [
            "http_url",
            "grpc_url",
            "api_key",
            "headers",
            "content_property",
            "metadata_properties",
        ],
        ["api_key", "headers"],
        [],
        ["collection_name", "default_similarity_threshold", "filters"],
    ),
}


class TestBuiltinBindings:
    @pytest.mark.parametrize("name", list(EXPECTED))
    def test_declares_the_agreed_fields(self, registry, name):
        editable, secret, internal, locked = EXPECTED[name]
        binding = registry.get_dataset_type(name)
        schema = binding.configuration_schema()
        assert binding.editable_fields() == editable
        assert binding.secret_fields() == secret
        assert fields_with_visibility(schema, Visibility.INTERNAL) == internal
        assert set(schema["properties"]) == set(editable) | set(internal) | set(locked)

    @pytest.mark.parametrize("name", list(EXPECTED))
    def test_every_property_carries_an_axis(self, registry, name):
        properties = registry.get_dataset_type(name).configuration_schema()[
            "properties"
        ]
        assert {p["axis"] for p in properties.values()} <= {"source", "vector_store"}

    def test_chroma_store_fields_sit_on_the_vector_store_axis(self, registry):
        for name in ("rss", "wordpress", "blogspot", "local_file"):
            properties = registry.get_dataset_type(name).configuration_schema()[
                "properties"
            ]
            assert properties["collectionName"]["axis"] == "vector_store"
            assert properties["httpPort"]["axis"] == "vector_store"

    def test_the_wire_keys_are_unchanged(self, registry):
        """Stored configurations and the frontend keep working as they are."""
        properties = registry.get_dataset_type("wordpress").configuration_schema()[
            "properties"
        ]
        assert properties["applicationPassword"]["format"] == "password"
        rss = registry.get_dataset_type("rss").configuration_schema()["properties"]
        assert "enum" in rss["pollIntervalSeconds"]

    def test_local_file_keeps_its_public_key_and_splits_without_overrides(
        self, registry
    ):
        """The source now prints the binding's historical key itself."""
        binding = registry.get_dataset_type("local_file")
        source_cfg, store_cfg = binding.split_config(
            {"ingestFileTypeOptions": [".md"], "collectionName": "c", "httpPort": 1}
        )
        assert source_cfg == {"ingestFileTypeOptions": [".md"]}
        assert store_cfg == {"collectionName": "c", "httpPort": 1}
        assert "split_config" not in vars(binding)
        assert "configuration_schema" not in vars(binding)


# ── split_config ─────────────────────────────────────────────────────────


class TestSplitConfig:
    def test_partitions_by_key_ownership_and_drops_strangers(self, registry):
        source_cfg, store_cfg = registry.get_dataset_type("wordpress").split_config(
            {
                "siteUrl": "https://w.example",
                "username": "u",
                "applicationPassword": "p",
                "collectionName": "c",
                "httpPort": 8000,
                "legacy": True,
            }
        )
        assert source_cfg == {
            "siteUrl": "https://w.example",
            "username": "u",
            "applicationPassword": "p",
        }
        assert store_cfg == {"collectionName": "c", "httpPort": 8000}

    def test_a_row_saved_with_python_names_still_splits(self, registry):
        """The old flat models took either spelling; rows may hold both."""
        source_cfg, store_cfg = registry.get_dataset_type("rss").split_config(
            {"collection_name": "c", "http_port": 1, "feed_urls": "https://a/f"}
        )
        assert source_cfg == {"feed_urls": "https://a/f"}
        assert store_cfg == {"collection_name": "c", "http_port": 1}

    def test_weaviate_sends_everything_to_the_store(self, registry):
        source_cfg, store_cfg = registry.get_dataset_type(
            "remote_weaviate"
        ).split_config({"http_url": "http://w", "collection_name": "C"})
        assert source_cfg == {}
        assert store_cfg == {"http_url": "http://w", "collection_name": "C"}

    def test_the_halves_build_the_axis_models(self, registry):
        """The axis models accept their aliases, so no key translation is needed."""
        from syft_space.components.sources.rss.rss_source import RssDatasetConfig

        source_cfg, _ = registry.get_dataset_type("rss").split_config(
            {"feedUrls": "https://a.example/feed", "collectionName": "c"}
        )
        assert RssDatasetConfig.model_validate(source_cfg).feed_urls == (
            "https://a.example/feed"
        )


# ── redact_configuration ─────────────────────────────────────────────────


class TestRedaction:
    def test_secret_scalars_are_dropped(self, registry):
        redacted = registry.get_dataset_type("wordpress").redact_configuration(
            {"siteUrl": "https://w.example", "applicationPassword": "p"}
        )
        assert redacted == {"siteUrl": "https://w.example"}

    def test_weaviate_api_key_no_longer_leaks(self, registry):
        redacted = registry.get_dataset_type("remote_weaviate").redact_configuration(
            {"http_url": "http://w", "api_key": "k", "collection_name": "C"}
        )
        assert redacted == {"http_url": "http://w", "collection_name": "C"}

    def test_a_secret_dict_keeps_its_keys_with_null_values(self, registry):
        redacted = registry.get_dataset_type("remote_weaviate").redact_configuration(
            {"headers": {"X-Cohere-Api-Key": "k", "X-OpenAI-Api-Key": "o"}}
        )
        assert redacted == {
            "headers": {"X-Cohere-Api-Key": None, "X-OpenAI-Api-Key": None}
        }

    def test_an_absent_secret_dict_stays_absent(self, registry):
        redacted = registry.get_dataset_type("remote_weaviate").redact_configuration(
            {"headers": None}
        )
        assert redacted == {}

    def test_a_binding_without_secrets_is_untouched(self, registry):
        cfg = {"feedUrls": "https://a.example/feed", "collectionName": "c"}
        assert registry.get_dataset_type("rss").redact_configuration(cfg) == cfg
        assert registry.get_dataset_type("rss").redact_configuration(cfg) is not cfg


# ── Custom binding sees the defaults ─────────────────────────────────────


class _SourceCfg(BaseModel):
    url: str = Field(..., json_schema_extra=cfg_flags(editable=True))
    token: str = Field(
        ..., json_schema_extra=cfg_flags(editable=True, visibility=Visibility.SECRET)
    )


class _StoreCfg(BaseModel):
    index: str = Field(...)


class _Provider:
    NAME = "fake_source"
    CONFIG_MODEL = _SourceCfg

    @classmethod
    def configuration_schema(cls):
        return cls.CONFIG_MODEL.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )


class _Store:
    NAME = "fake_store"
    CONFIG_MODEL = _StoreCfg

    @classmethod
    def configuration_schema(cls):
        return cls.CONFIG_MODEL.model_json_schema(
            schema_generator=ConfigSchemaGenerator
        )


class _Binding(BaseDatasetType):
    NAME = "fake_binding"
    SOURCE_PROVIDER_CLS = _Provider  # type: ignore[assignment]
    VECTOR_STORE_CLS = _Store  # type: ignore[assignment]


def test_a_binding_declares_nothing_itself():
    """Flags live on the axis models; the binding only composes and reads."""
    assert _Binding.editable_fields() == ["url", "token"]
    assert _Binding.secret_fields() == ["token"]
    assert _Binding.split_config({"url": "u", "token": "t", "index": "i"}) == (
        {"url": "u", "token": "t"},
        {"index": "i"},
    )
    assert _Binding.redact_configuration({"url": "u", "token": "t"}) == {"url": "u"}


def test_ownership_comes_from_the_models_not_a_naming_rule():
    """An alias that is not plain camelCase still routes under both spellings."""

    class SourceCfg(BaseModel):
        grpc_url: str = Field(..., alias="grpcURL")
        model_config = {"populate_by_name": True}

    class Provider(_Provider):
        CONFIG_MODEL = SourceCfg

    class Binding(_Binding):
        NAME = "odd_alias"
        SOURCE_PROVIDER_CLS = Provider  # type: ignore[assignment]

    assert Binding.split_config({"grpcURL": "a", "index": "i"}) == (
        {"grpcURL": "a"},
        {"index": "i"},
    )
    assert Binding.split_config({"grpc_url": "a"}) == ({"grpc_url": "a"}, {})


def test_a_python_name_shared_across_axes_is_refused():
    """``index`` on the source would collide with the store's ``index``."""

    class SourceCfg(BaseModel):
        index: str = Field(..., alias="sourceIndex")

    class Provider(_Provider):
        CONFIG_MODEL = SourceCfg

    class Binding(_Binding):
        NAME = "colliding"
        SOURCE_PROVIDER_CLS = Provider  # type: ignore[assignment]

    with pytest.raises(ValueError, match="both axes"):
        Binding.split_config({})
