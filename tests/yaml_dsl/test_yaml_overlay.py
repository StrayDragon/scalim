from pathlib import Path

import pytest

from scalim.dsl.by_yaml import UNSET, RunOverrides, compile
from scalim.dsl.by_yaml.config_parsing.error_envelope import ScalimYamlValidationError
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
  loader: tests.fixtures.mock_loaders.mock_loader
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
                "to": {"book": "report", "sheet": "Detail"},
                "fields": ["amount", "order_id"],
            }
        ],
        resources={
            "books": {
                "report": {
                    "kind": "xlsx_file",
                    "path": out_path,
                }
            }
        },
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]), overrides=overrides)
    request = compilation.request
    assert request.output_composition is not None
    assert len(request.output_composition.targets) == 1

    target = request.output_composition.targets[0]
    assert target.output.format == "excel"
    assert target.output.path == out_path
    assert target.output.sheet_name == "Detail"
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
  loader: tests.fixtures.mock_loaders.mock_loader
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
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]), overrides=overrides)


def test_compile_overrides_outputs_rejects_unsupported_keys(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_unsupported_keys
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    overrides = RunOverrides(
        outputs=[
            {
                "name": "detail",
                "to": {"file": "detail_csv"},
                "fields": ["order_id"],
                "where": "order_id != ''",
            }
        ]
    )
    with pytest.raises(ValueError, match=r"unsupported keys: where"):
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]), overrides=overrides)


@pytest.mark.parametrize(
    "outputs,exc_type,match",
    [
        ({"name": "detail"}, TypeError, r"overrides\.outputs must be a list"),
        (["detail"], TypeError, r"overrides\.outputs\.0 must be an object"),
        (
            [{"name": "detail", "container": {"type": "csv", "path": "./out.csv"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.container was removed",
        ),
        (
            [{"name": "detail", "to": "report", "fields": ["order_id"]}],
            TypeError,
            r"overrides\.outputs\.0\.to must be an object",
        ),
        (
            [{"name": "detail", "write": "append", "fields": ["order_id"]}],
            TypeError,
            r"overrides\.outputs\.0\.write must be an object",
        ),
        (
            [{"name": "detail", "write": {"mode": 123}, "fields": ["order_id"]}],
            TypeError,
            r"overrides\.outputs\.0\.write\.mode must be a string",
        ),
        (
            [{"to": {"file": "detail_csv"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.name is required",
        ),
        (
            [{"name": "bad-name", "to": {"file": "detail_csv"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.name='bad-name' is invalid",
        ),
        (
            [
                {"name": "detail", "to": {"file": "detail_csv"}, "fields": ["order_id"]},
                {"name": "detail", "to": {"file": "detail_csv"}, "fields": ["order_id"]},
            ],
            ValueError,
            r"overrides\.outputs has duplicate output name: detail",
        ),
        (
            [{"name": "detail", "to": {"file": "detail_csv"}, "fields": "order_id"}],
            TypeError,
            r"overrides\.outputs\.0\.fields must be a list",
        ),
        (
            [{"name": "detail", "to": {"file": "detail_csv"}, "fields": []}],
            ValueError,
            r"overrides\.outputs\.0\.fields must not be empty",
        ),
        (
            [{"name": "detail", "to": {"file": "detail_csv"}, "fields": [123]}],
            TypeError,
            r"overrides\.outputs\.0\.fields\.0 must be a field_id string",
        ),
        (
            [{"name": "detail", "to": {"file": "detail_csv"}, "fields": [""]}],
            ValueError,
            r"overrides\.outputs\.0\.fields\.0 must not be empty",
        ),
        (
            [{"name": "detail", "to": {"file": "detail_csv"}, "fields": ["unknown"]}],
            ValueError,
            r"overrides\.outputs\.0\.fields reference unknown fields: unknown",
        ),
        (
            [{"name": "detail", "to": {"file": "detail_csv", "book": "report"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.to must declare exactly one of to\.file or to\.book",
        ),
        (
            [
                {
                    "name": "detail",
                    "to": {"file": "detail_csv"},
                    "write": {"mode": "append"},
                    "fields": ["order_id"],
                }
            ],
            ValueError,
            r"overrides\.outputs\.0\.write\.mode only apply to book outputs",
        ),
        (
            [{"name": "detail", "to": {"sheet": "Detail"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.to must declare exactly one of to\.file or to\.book",
        ),
        (
            [{"name": "detail", "to": {"file": "detail_csv"}, "write": {"header_fields_output_by": "bad"}, "fields": ["order_id"]}],
            ValueError,
            r"overrides\.outputs\.0\.write\.header_fields_output_by='bad' is invalid",
        ),
    ],
    ids=[
        "outputs-not-list",
        "item-not-object",
        "container-removed",
        "to-not-object",
        "write-not-object",
        "write-mode-not-string",
        "name-required",
        "name-invalid-pattern",
        "duplicate-name",
        "fields-not-list",
        "fields-empty",
        "fields-item-not-string",
        "fields-item-empty",
        "fields-unknown",
        "to-file-and-book-conflict",
        "file-output-book-write-conflict",
        "sheet-without-binding",
        "write-header-by-invalid",
    ],
)
def test_compile_overrides_outputs_rejects_invalid_payloads(tmp_path: Path, outputs, exc_type, match: str) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_invalid
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    overrides = RunOverrides(outputs=outputs)
    with pytest.raises(exc_type, match=match):
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]), overrides=overrides)


def test_compile_overrides_outputs_supports_init_var_path(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_overrides_outputs_init_var
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    output_path = str(tmp_path / "out.csv")
    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
        init_vars={"out_path": output_path},
        overrides=RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "to": {"file": "detail_csv"},
                    "fields": ["order_id"],
                }
            ],
            resources={"files": {"detail_csv": {"kind": "csv_file", "path": {"$init_var": "out_path"}}}},
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
""",
    )

    output_path = tmp_path / "out.csv"
    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
        overrides=RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "to": {"file": "detail_csv"},
                    "fields": ["order_id"],
                }
            ],
            resources={"files": {"detail_csv": {"kind": "csv_file", "path": output_path}}},
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
meta: true
sources: {}
""",
    )

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
        overrides=RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "to": {"file": "detail_csv"},
                    "fields": ["order_id"],
                }
            ],
            resources={"files": {"detail_csv": {"kind": "csv_file", "path": "./out.csv"}}},
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id, name: ID}
    amount: {extract: amount, name: ID}
sources: {}
""",
    )

    with pytest.raises(ValueError, match=r"Duplicate effective field display names detected"):
        _ = compile(
            str(yaml_path),
            allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
            overrides=RunOverrides(
                outputs=[
                    {
                        "name": "detail",
                        "to": {"file": "detail_csv"},
                        "write": {"header_fields_output_by": "name"},
                        "fields": ["order_id", "amount"],
                    }
                ],
                resources={"files": {"detail_csv": {"kind": "csv_file", "path": "./out.csv"}}},
            ),
        )


def test_should_validate_unique_field_names_skips_field_id_headers() -> None:
    from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.by_yaml.runtime import compiler as compiler_mod
    from scalim.dsl.by_yaml.schema_dsl.models import OutputTargetConfig, OutputToConfig, OutputWriteConfig

    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: overlay_unique_names_skip_field_id
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out.csv}
"""
    )

    outputs = (
        OutputTargetConfig(
            name="base",
            from_=None,
            to=OutputToConfig(file="detail_csv"),
            write=OutputWriteConfig(header_fields_output_by="field_id"),
            fields=("order_id",),
            where=None,
            aggregate=None,
            requires=(),
        ),
        OutputTargetConfig(
            name="derived",
            from_="base",
            fields=("order_id",),
            where=None,
            aggregate=None,
            requires=(),
        ),
    )

    assert compiler_mod._should_validate_unique_effective_field_display_names(config, outputs) is False  # noqa: SLF001


def test_should_validate_unique_field_names_includes_books_outputs() -> None:
    from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.by_yaml.runtime import compiler as compiler_mod
    from scalim.dsl.by_yaml.schema_dsl.models import OutputTargetConfig, OutputToConfig

    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: overlay_unique_names_books
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources:
  books:
    report: {kind: xlsx_file, path: ./out.xlsx}
"""
    )

    outputs = (
        OutputTargetConfig(
            name="detail",
            to=OutputToConfig(book="report", sheet="明细"),
            fields=("order_id",),
            where=None,
            aggregate=None,
            requires=(),
        ),
    )

    assert compiler_mod._should_validate_unique_effective_field_display_names(config, outputs) is True  # noqa: SLF001


def test_validate_unique_field_names_rejects_duplicates_by_default(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_default
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
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
    to: {file: detail_csv}
    fields: [order_id, amount]
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out.csv}
""",
    )

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))
    assert any("Duplicate effective field display names" in env.message for env in excinfo.value.errors)
    assert any("'ID'" in env.message for env in excinfo.value.errors)
    assert any("main_source.fields.order_id" in env.message for env in excinfo.value.errors)
    assert any("main_source.fields.amount" in env.message for env in excinfo.value.errors)


def test_validate_unique_field_names_rejects_duplicates_for_books_by_default(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_books_default
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
      name: ID
    amount:
      extract: amount
      name: ID
sources: {}
resources:
  books:
    report:
      kind: xlsx_file
      path: ./out.xlsx
outputs:
  - name: detail
    to: {book: report, sheet: 明细}
    fields: [order_id, amount]
""",
    )

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))
    assert any("Duplicate effective field display names" in env.message for env in excinfo.value.errors)


def test_validate_unique_field_names_can_be_disabled(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_unique_names_disabled
validate_unique_field_names: false
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
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
    to: {file: detail_csv}
    fields: [order_id, amount]
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out.csv}
""",
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))
    assert compilation.request.output_composition is not None


def test_compile_viz_config_override_enables_viz_without_yaml_observability(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_enable
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
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

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]), overrides=overrides)
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is viz_config


def test_compile_viz_config_override_none_disables_viz(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_disable
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
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

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]), overrides=overrides)
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is None


def test_compile_viz_config_override_overrides_yaml_observability(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_override
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
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

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]), overrides=overrides)
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
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
                "loader": "tests.fixtures.mock_loaders.mock_loader",
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
