from pathlib import Path

import pytest

from scalim.dsl.by_yaml import UNSET, RunOverrides, compile
from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.ob.presets.viz import VizObserverConfig


def _write_yaml(tmp_path: Path, text: str) -> Path:
    yaml_path = tmp_path / "overlay.yaml"
    yaml_path.write_text(text.strip() + "\n", encoding="utf-8")
    return yaml_path


def test_unset_repr() -> None:
    assert repr(UNSET) == "UNSET"


def test_compile_applies_output_overrides_and_export_layout(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
      name: Order ID
    amount:
      extract: amount
      name: Amount
sources: {}
""",
    )

    out_path = str(tmp_path / "out.xlsx")
    overrides = RunOverrides(
        outputs=[
            {
                "name": "detail",
                "container": {
                    "type": "workbook",
                    "path": out_path,
                    "sheet": "Detail",
                    "encoding": "utf-16",
                    "include_header": True,
                    "header_fields_output_by": "name",
                },
                "fields": ["amount", "order_id"],
            }
        ]
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)
    request = compilation.request
    assert request.output_composition is not None
    assert len(request.output_composition.targets) == 1

    target = request.output_composition.targets[0]
    assert target.output.format == "excel"
    assert target.output.path == out_path
    assert target.output.sheet_name == "Detail"
    assert target.output.encoding == "utf-16"
    assert target.output.include_header is True
    assert target.layout.field_ids == ("amount", "order_id")
    assert target.layout.header_names == ("Amount", "Order ID")


def test_compile_overrides_outputs_empty_rejected(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_empty
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
    amount:
      extract: amount
sources: {}
""",
    )

    overrides = RunOverrides(outputs=[])
    with pytest.raises(ValueError, match=r"overrides\.outputs cannot be empty"):
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)


def test_compile_overrides_outputs_rejects_unsupported_keys(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_unsupported_keys
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    overrides = RunOverrides(
        outputs=[
            {
                "name": "detail",
                "container": {"type": "csv", "path": "./out.csv"},
                "fields": ["order_id"],
                "where": "order_id != ''",
            }
        ]
    )
    with pytest.raises(ValueError, match=r"unsupported keys: where"):
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)


@pytest.mark.parametrize(
    "outputs,exc_type,match",
    [
        ({"name": "detail"}, TypeError, r"overrides\.outputs must be a list"),
        (["detail"], TypeError, r"overrides\.outputs\.0 must be an object"),
        (
            [{"name": "detail", "container": "csv", "fields": ["order_id"]}],
            TypeError,
            r"overrides\.outputs\.0\.container must be an object",
        ),
        (
            [{"name": "detail", "container": {}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.container\.type is required",
        ),
        (
            [{"name": "detail", "container": {"type": "json"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.container\.type='json' is invalid",
        ),
        (
            [{"name": "detail", "container": {"type": "workbook"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.container\.path is required for workbook outputs",
        ),
        (
            [{"name": "detail", "container": {"type": "csv", "path": 123}, "fields": ["order_id"]}],
            TypeError,
            r"overrides\.outputs\.0\.container\.path must be a string",
        ),
        (
            [
                {
                    "name": "detail",
                    "container": {"type": "csv", "path": "./out.csv", "header_fields_output_by": "bad"},
                    "fields": ["order_id"],
                }
            ],
            ValueError,
            r"overrides\.outputs\.0\.container\.header_fields_output_by='bad' is invalid",
        ),
        (
            [{"name": "detail", "container": {"type": "csv", "path": "./out.csv", "streaming": False}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.container\.streaming must be true",
        ),
        (
            [{"name": "detail", "container": {"type": "csv", "path": "./out.csv", "sheet": "Detail"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.container\.sheet is only allowed for type=workbook",
        ),
        (
            [
                {
                    "name": "detail",
                    "container": {"type": "csv", "path": "./out.csv", "allow_formulas": True},
                    "fields": ["order_id"],
                }
            ],
            ValueError,
            r"overrides\.outputs\.0\.container\.allow_formulas is only allowed for type=workbook",
        ),
        (
            [{"name": "detail", "container": {"type": "csv", "path": "./out.csv", "write_lock": True}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.container\.write_lock is only allowed for type=workbook",
        ),
        (
            [{"container": {"type": "csv", "path": "./out.csv"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.name is required",
        ),
        (
            [{"name": "bad-name", "container": {"type": "csv", "path": "./out.csv"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.name='bad-name' is invalid",
        ),
        (
            [
                {"name": "detail", "container": {"type": "csv", "path": "./out.csv"}, "fields": ["order_id"]},
                {"name": "detail", "container": {"type": "csv", "path": "./out.csv"}, "fields": ["order_id"]},
            ],
            ValueError,
            r"overrides\.outputs has duplicate output name: detail",
        ),
        (
            [{"name": "detail", "container": {"type": "csv", "path": "./out.csv"}, "fields": "order_id"}],
            TypeError,
            r"overrides\.outputs\.0\.fields must be a list",
        ),
        (
            [{"name": "detail", "container": {"type": "csv", "path": "./out.csv"}, "fields": []}],
            ValueError,
            r"overrides\.outputs\.0\.fields must not be empty",
        ),
        (
            [{"name": "detail", "container": {"type": "csv", "path": "./out.csv"}, "fields": [123]}],
            TypeError,
            r"overrides\.outputs\.0\.fields\.0 must be a field_id string",
        ),
        (
            [{"name": "detail", "container": {"type": "csv", "path": "./out.csv"}, "fields": [""]}],
            ValueError,
            r"overrides\.outputs\.0\.fields\.0 must not be empty",
        ),
        (
            [{"name": "detail", "container": {"type": "csv", "path": "./out.csv"}, "fields": ["unknown"]}],
            ValueError,
            r"overrides\.outputs\.0\.fields reference unknown fields: unknown",
        ),
    ],
    ids=[
        "outputs-not-list",
        "item-not-object",
        "container-not-object",
        "container-type-required",
        "container-type-invalid",
        "workbook-path-required",
        "path-invalid-type",
        "header-by-invalid",
        "streaming-must-be-true",
        "sheet-only-workbook",
        "allow-formulas-only-workbook",
        "write-lock-only-workbook",
        "name-required",
        "name-invalid-pattern",
        "duplicate-name",
        "fields-not-list",
        "fields-empty",
        "fields-item-not-string",
        "fields-item-empty",
        "fields-unknown",
    ],
)
def test_compile_overrides_outputs_rejects_invalid_payloads(tmp_path: Path, outputs, exc_type, match: str) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_invalid
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    overrides = RunOverrides(outputs=outputs)
    with pytest.raises(exc_type, match=match):
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)


def test_compile_overrides_outputs_supports_init_var_path(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_init_var
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    output_path = str(tmp_path / "out.csv")
    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.conftest"]),
        init_vars={"out_path": output_path},
        overrides=RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "container": {"type": "csv", "path": {"$init_var": "out_path"}},
                    "fields": ["order_id"],
                }
            ]
        ),
    )

    assert compilation.request.output_composition is not None
    assert compilation.request.output_composition.targets[0].output.path == output_path


def test_compile_overrides_outputs_supports_pathlike_path(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_pathlike
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    output_path = tmp_path / "out.csv"
    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.conftest"]),
        overrides=RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "container": {"type": "csv", "path": output_path},
                    "fields": ["order_id"],
                }
            ]
        ),
    )

    assert compilation.request.output_composition is not None
    assert compilation.request.output_composition.targets[0].output.path == str(output_path)


def test_compile_overrides_outputs_disables_implicit_meta_without_workbook(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_meta
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: {extract: order_id}
outputs:
  - name: detail
    container: {type: workbook, path: ./report.xlsx, sheet: Detail}
    fields: [order_id]
meta: true
sources: {}
""",
    )

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.conftest"]),
        overrides=RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "container": {"type": "csv", "path": "./out.csv"},
                    "fields": ["order_id"],
                }
            ]
        ),
    )

    assert compilation.request.output_composition is not None
    assert compilation.request.output_composition.meta_sheet is None


def test_validate_unique_field_names_runtime_rejects_duplicates_triggered_by_overrides(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_runtime
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: {extract: order_id, name: ID}
    amount: {extract: amount, name: ID}
sources: {}
""",
    )

    with pytest.raises(ValueError, match=r"Duplicate effective field display names detected"):
        _ = compile(
            str(yaml_path),
            allowed_modules=frozenset(["tests.conftest"]),
            overrides=RunOverrides(
                outputs=[
                    {
                        "name": "detail",
                        "container": {"type": "csv", "path": "./out.csv", "header_fields_output_by": "name"},
                        "fields": ["order_id", "amount"],
                    }
                ]
            ),
        )


def test_should_validate_unique_field_names_skips_outputs_without_container() -> None:
    from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.by_yaml.runtime import compiler as compiler_mod
    from scalim.dsl.by_yaml.schema_dsl.models import OutputContainerConfig, OutputTargetConfig

    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: overlay_unique_names_skip_container
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
"""
    )

    outputs = (
        OutputTargetConfig(
            name="base",
            from_=None,
            container=OutputContainerConfig(type="csv", path="./out.csv", header_fields_output_by="field_id"),
            fields=("order_id",),
            where=None,
            aggregate=None,
            requires=(),
        ),
        OutputTargetConfig(
            name="derived",
            from_="base",
            container=None,
            fields=("order_id",),
            where=None,
            aggregate=None,
            requires=(),
        ),
    )

    assert compiler_mod._should_validate_unique_effective_field_display_names(config, outputs) is False  # noqa: SLF001


def test_validate_unique_field_names_rejects_duplicates_by_default(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_default
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
      name: ID
    amount:
      extract: amount
      name: ID
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields: [order_id, amount]
""",
    )

    with pytest.raises(ConfigValidationError) as excinfo:
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]))
    assert any("Duplicate effective field display names" in msg for msg in excinfo.value.errors)
    assert any("'ID'" in msg for msg in excinfo.value.errors)
    assert any("main_source.fields.order_id" in msg for msg in excinfo.value.errors)
    assert any("main_source.fields.amount" in msg for msg in excinfo.value.errors)


def test_validate_unique_field_names_can_be_disabled(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_disabled
validate_unique_field_names: false
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
      name: ID
    amount:
      extract: amount
      name: ID
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields: [order_id, amount]
""",
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]))
    assert compilation.request.output_composition is not None


def test_compile_viz_config_override_enables_viz_without_yaml_observability(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_enable
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    viz_config = VizObserverConfig(
        output_path=str(tmp_path / "events.jsonl"),
        snapshot_path=str(tmp_path / "snapshot.json"),
    )
    overrides = RunOverrides(viz_config=viz_config)

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is viz_config


def test_compile_viz_config_override_none_disables_viz(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_disable
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
observability:
  viz:
    enabled: true
    output_dir: ./tmp
""",
    )

    overrides = RunOverrides(viz_config=None)

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is None


def test_compile_viz_config_override_overrides_yaml_observability(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_override
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
observability:
  performance:
    enabled: true
    metrics: [duration]
    sampling_interval: 1
    report:
      format: none
""",
    )

    viz_config = VizObserverConfig(
        output_path=str(tmp_path / "events.jsonl"),
        snapshot_path=str(tmp_path / "snapshot.json"),
    )
    overrides = RunOverrides(viz_config=viz_config)

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is viz_config


def test_compile_keeps_null_batch_size_from_yaml(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_batch_size_null
batch_size: null
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]))
    config = compilation.config
    request = compilation.request

    assert config.batch_size is None
    assert request.batch_size is None


def test_compile_batch_size_option_overrides_yaml_null(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_batch_size_override
batch_size: null
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.conftest"]),
        batch_size=256,
    )
    request = compilation.request

    assert request.batch_size == 256


def test_loader_parse_config_rejects_invalid_validate_unique_field_names_type() -> None:
    from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.by_yaml.config_parsing.models import RawDemand

    loader = YamlDemandLoader()
    raw = RawDemand.from_raw(
        {
            "name": "overlay_unique_names_type_error",
            "validate_unique_field_names": 1,
            "main_source": {
                "source_id": "orders",
                "loader": "tests.conftest.mock_loader",
                "fields": {"order_id": {"extract": "order_id"}},
            },
            "sources": {},
            "relations": {},
            "fields": {},
            "outputs": [],
        }
    )
    with pytest.raises(TypeError, match=r"validate_unique_field_names must be a boolean"):
        loader._parse_config(raw)  # type: ignore[attr-defined]
