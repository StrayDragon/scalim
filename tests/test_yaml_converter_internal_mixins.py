import pytest

from scalim.dsl.by_yaml.runtime._internal.conversion_relations import ConfigToIRConversionRelationMixin
from scalim.dsl.by_yaml.runtime._internal.conversion_sources import ConfigToIRConversionSourceMixin
from scalim.dsl.by_yaml.runtime.errors import ConversionError


@pytest.mark.parametrize(
    ("method_name", "kwargs"),
    [
        ("_get_lookup_cast_fn", {"lookup_cast": None, "is_multi": False}),
        ("_create_binding", {"bind_config": None, "static_params": None, "key_field": "id"}),
    ],
)
def test_relation_mixin_hook_placeholders_raise_not_implemented(method_name: str, kwargs: dict) -> None:
    mixin = ConfigToIRConversionRelationMixin()
    method = getattr(mixin, method_name)

    with pytest.raises(NotImplementedError):
        method(**kwargs)


@pytest.mark.parametrize(
    ("method_name", "match"),
    [
        ("_require_sources_ir", "Source IR map is not initialized"),
        ("_require_relation_steps", "Relation steps are not initialized"),
        ("_require_relation_adjacency", "Relation adjacency is not initialized"),
        ("_require_source_field_id_map", "Source field id map is not initialized"),
        ("_require_source_data_key_map", "Source data key map is not initialized"),
    ],
)
def test_relation_mixin_require_helpers_raise_clear_errors(method_name: str, match: str) -> None:
    mixin = ConfigToIRConversionRelationMixin()
    method = getattr(mixin, method_name)

    with pytest.raises(ConversionError, match=match):
        method()


@pytest.mark.parametrize(
    ("method_name", "match"),
    [
        ("_require_resolver", "Reference resolver is not initialized"),
        ("_require_compute_engine", "Compute engine is not initialized"),
    ],
)
def test_source_mixin_require_helpers_raise_clear_errors(method_name: str, match: str) -> None:
    mixin = ConfigToIRConversionSourceMixin()
    method = getattr(mixin, method_name)

    with pytest.raises(ConversionError, match=match):
        method()
