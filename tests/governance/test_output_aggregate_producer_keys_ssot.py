from types import SimpleNamespace

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.parsers import outputs as outputs_parser
from scalim.dsl.yaml_dsl.runtime import introspection as introspection_mod
from scalim.dsl.yaml_dsl.runtime import output_composition_yaml as oc_yaml
from scalim.dsl.yaml_dsl.schema_dsl.models import outputs as schema_outputs
from scalim.dsl.yaml_dsl.schema_dsl.output_enums import (
    AGG_METRIC_PRODUCER_KEYS,
    AGG_POST_PRODUCER_KEYS,
    AGG_RANK_PRODUCER_KEYS,
)


def test_output_aggregate_producer_key_enums_are_shared_across_layers() -> None:
    assert outputs_parser._AGG_FUNC_KEYS is AGG_METRIC_PRODUCER_KEYS  # noqa: SLF001
    assert outputs_parser._RANK_FUNC_KEYS is AGG_RANK_PRODUCER_KEYS  # noqa: SLF001
    assert outputs_parser._POST_FUNC_KEYS is AGG_POST_PRODUCER_KEYS  # noqa: SLF001

    assert oc_yaml._AGG_FUNC_KEYS is AGG_METRIC_PRODUCER_KEYS  # noqa: SLF001
    assert oc_yaml._RANK_FUNC_KEYS is AGG_RANK_PRODUCER_KEYS  # noqa: SLF001
    assert oc_yaml._POST_FUNC_KEYS is AGG_POST_PRODUCER_KEYS  # noqa: SLF001

    assert introspection_mod._AGG_FUNC_KEYS is AGG_METRIC_PRODUCER_KEYS  # noqa: SLF001
    assert introspection_mod._RANK_FUNC_KEYS is AGG_RANK_PRODUCER_KEYS  # noqa: SLF001
    assert introspection_mod._POST_FUNC_KEYS is AGG_POST_PRODUCER_KEYS  # noqa: SLF001


def test_validate_output_aggregate_producer_keys_schema_raises_on_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    # 覆盖 schema guard 的异常分支(避免 100% 覆盖率门禁掉落).
    fake_one_of = [
        {"required": ["count"]},
        {"required": ["rank"]},
        {"required": ["x", "y"]},  # 非 1 个元素的 required: 应被忽略
    ]
    fake_schema = {"additionalProperties": {"oneOf": fake_one_of}}

    fake_output_aggregate_config = SimpleNamespace(
        __dataclass_fields__={
            "fields": SimpleNamespace(metadata={"schema": {"schema": fake_schema}}),
        }
    )

    monkeypatch.setattr(schema_outputs, "OutputAggregateConfig", fake_output_aggregate_config, raising=True)

    with pytest.raises(ValueError, match="schema 覆盖不一致"):
        schema_outputs._validate_output_aggregate_producer_keys_schema()  # noqa: SLF001


def test_validate_output_aggregate_producer_keys_schema_ignores_non_str_required_items(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = tuple(AGG_METRIC_PRODUCER_KEYS + AGG_RANK_PRODUCER_KEYS + AGG_POST_PRODUCER_KEYS)
    fake_one_of = [{"required": [1]}] + [{"required": [k]} for k in expected]
    fake_schema = {"additionalProperties": {"oneOf": fake_one_of}}

    fake_output_aggregate_config = SimpleNamespace(
        __dataclass_fields__={
            "fields": SimpleNamespace(metadata={"schema": {"schema": fake_schema}}),
        }
    )
    monkeypatch.setattr(schema_outputs, "OutputAggregateConfig", fake_output_aggregate_config, raising=True)

    schema_outputs._validate_output_aggregate_producer_keys_schema()  # noqa: SLF001
