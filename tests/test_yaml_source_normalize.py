from pathlib import Path

import pytest

import scalim.dsl.by_yaml.config_parsing.validator as validator_module
from scalim.dsl.by_yaml import run
from scalim.sinks.sink_memory import InMemoryRowSink

import tests.source_normalize_loaders as loaders


def _write_yaml(tmp_path: Path, text: str) -> Path:
    yaml_path = tmp_path / "normalize.yaml"
    yaml_path.write_text(text.strip() + "\n", encoding="utf-8")
    return yaml_path


def _assert_validation_errors(config: dict, *expected_messages: str) -> None:
    validator = validator_module.ConfigValidator()
    with pytest.raises(validator_module.ConfigValidationError) as exc:
        validator.validate(config)
    errors = exc.value.errors
    for message in expected_messages:
        assert any(message in msg for msg in errors)


def test_validator_rejects_main_source_normalize() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.source_normalize_loaders:load_orders_main",
            "normalize": {"kind": "index_by_key", "key_field": "order_id"},
        },
        "sources": {},
    }
    _assert_validation_errors(config, "main_source.normalize")


def test_validator_requires_normalize_key_field() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.source_normalize_loaders:load_orders_main",
            "fields": {"order_id": {"extract": "order_id"}},
        },
        "sources": {
            "recommends": {
                "loader": "tests.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": {"kind": "index_by_key"},
            }
        },
    }
    _assert_validation_errors(config, "normalize.key_field")


def test_validator_requires_normalize_to_be_mapping() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": "bad",
            }
        },
    }
    _assert_validation_errors(config, "normalize' must be a dictionary")


def test_validator_rejects_unknown_normalize_kind() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": {"kind": "bad", "key_field": "order_id"},
            }
        },
    }
    _assert_validation_errors(config, "normalize.kind must be 'index_by_key'")


def test_validator_rejects_normalize_for_composite_key() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.source_normalize_loaders:load_recommends_list",
                "key": ["region_id", "institution_id"],
                "normalize": {"kind": "index_by_key", "key_field": "region_id"},
            }
        },
    }
    _assert_validation_errors(config, "does not support composite key yet")


def test_validator_rejects_normalize_key_field_mismatch() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": {"kind": "index_by_key", "key_field": "other"},
            }
        },
    }
    _assert_validation_errors(config, "normalize.key_field must equal sources")


def test_validator_rejects_normalize_on_conflict_invalid() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": {"kind": "index_by_key", "key_field": "order_id", "on_conflict": "bad"},
            }
        },
    }
    _assert_validation_errors(config, "normalize.on_conflict must be one of")


def test_run_applies_normalize_index_by_key_before_extract(tmp_path: Path) -> None:
    loaders.reset_call_counts()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: normalize_non_cached
main_source:
  source_id: orders
  loader: tests.source_normalize_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id

sources:
  recommends:
    loader: tests.source_normalize_loaders:load_recommends_list
    key: order_id
    normalize:
      kind: index_by_key
      key_field: order_id
    fields:
      recommend_score:
        extract: payload.score
        relation:
          steps:
            - from: orders.order_id
              to: recommends.order_id

output:
  fields:
    - field_id: order_id
    - field_id: recommend_score
""",
    )

    sink = InMemoryRowSink()
    _ = run(str(yaml_path), allowed_modules=frozenset(["tests.source_normalize_loaders"]), sink=sink)

    rows = sink.get_data()
    by_order_id = {row["order_id"]: row for row in rows}
    assert by_order_id[101]["recommend_score"] == 0.9
    assert by_order_id[102]["recommend_score"] == 0.7
    assert loaders.CALL_COUNTS["recommends"] >= 1


def test_run_preload_forever_caches_normalized_mapping(tmp_path: Path) -> None:
    loaders.reset_call_counts()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: normalize_preload
main_source:
  source_id: orders
  loader: tests.source_normalize_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id

sources:
  recommends:
    loader: tests.source_normalize_loaders:load_recommends_list
    key: order_id
    cache_mode: preload_forever
    normalize:
      kind: index_by_key
      key_field: order_id
    fields:
      recommend_score:
        extract: payload.score
        relation:
          steps:
            - from: orders.order_id
              to: recommends.order_id

output:
  fields:
    - field_id: order_id
    - field_id: recommend_score
""",
    )

    sink = InMemoryRowSink()
    _ = run(str(yaml_path), allowed_modules=frozenset(["tests.source_normalize_loaders"]), sink=sink)

    rows = sink.get_data()
    by_order_id = {row["order_id"]: row for row in rows}
    assert by_order_id[101]["recommend_score"] == 0.9
    assert by_order_id[102]["recommend_score"] == 0.7
    assert loaders.CALL_COUNTS["recommends"] == 1


def test_converter_rejects_unknown_normalize_kind() -> None:
    from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.by_yaml.runtime.errors import ConversionError
    from scalim.dsl.by_yaml.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter(allow_unsafe_resolver=True)
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.conftest.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="bad", key_field="id"),
    )
    with pytest.raises(ConversionError, match="normalize\\.kind must be 'index_by_key'"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_missing_normalize_key_field() -> None:
    from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.by_yaml.runtime.errors import ConversionError
    from scalim.dsl.by_yaml.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter(allow_unsafe_resolver=True)
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.conftest.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="index_by_key", key_field=""),
    )
    with pytest.raises(ConversionError, match="normalize\\.key_field is required"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_invalid_normalize_on_conflict() -> None:
    from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.by_yaml.runtime.errors import ConversionError
    from scalim.dsl.by_yaml.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter(allow_unsafe_resolver=True)
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.conftest.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="index_by_key", key_field="id", on_conflict="bad"),
    )
    with pytest.raises(ConversionError, match="normalize\\.on_conflict must be one of"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_normalize_for_composite_key() -> None:
    from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.by_yaml.runtime.errors import ConversionError
    from scalim.dsl.by_yaml.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter(allow_unsafe_resolver=True)
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.conftest.mock_loader",
        key=("a", "b"),
        normalize=NormalizeConfig(kind="index_by_key", key_field="a"),
    )
    with pytest.raises(ConversionError, match="does not support composite key yet"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_normalize_key_field_mismatch() -> None:
    from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.by_yaml.runtime.errors import ConversionError
    from scalim.dsl.by_yaml.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter(allow_unsafe_resolver=True)
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.conftest.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="index_by_key", key_field="other"),
    )
    with pytest.raises(ConversionError, match="normalize\\.key_field must equal sources\\.s1\\.key"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]
