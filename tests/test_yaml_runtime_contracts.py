from pathlib import Path
from typing import List

import pytest

from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml import run
from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.runtime.errors import AllowlistRequiredError, ConversionError
from scalim.dsl.by_yaml.schema_dsl.builder import build_demand_schema
from scalim.dsl.by_yaml.schema_dsl.models import BindConfig
from scalim.sinks.sink_csv import CSVSink, ColumnCSVSink


def _write_simple_yaml(tmp_path: Path, loader_path: str) -> Path:
    yaml_path = tmp_path / "test.yaml"
    yaml_path.write_text(
        """
name: test
main_source:
  source_id: orders
  loader: {loader_path}
  fields:
    order_id:
      field: order_id
sources: {{}}
""".format(loader_path=loader_path),
        encoding="utf-8",
    )
    return yaml_path


class TestLookupCastAndBindDefaults:
    def test_lookup_cast_object_parsed(self) -> None:
        yaml_content = """
name: test_lookup_cast
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      field: order_id
    customer_id:
      field: customer_id
relations:
  r1: &r1
    steps:
      - from: orders.customer_id
        to: customers.customer_id
        lookup_cast: {name: sep_first, sep: ","}
        to_bind: {use_keys: {param: ids}}
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    bind: {use_keys: {param: ids}}
    fields:
      customer_name:
        field: customer_name
        relation: *r1
"""
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        step = config.relations["r1"].steps[0]
        assert step.lookup_cast is not None
        assert step.lookup_cast.name == "sep_first"
        assert step.lookup_cast.sep == ","

    def test_bind_defaults_to_keys_set(self) -> None:
        yaml_content = """
name: test_bind_defaults
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      field: order_id
    customer_id:
      field: customer_id
relations:
  r1: &r1
    steps:
      - from: orders.customer_id
        to: customers.customer_id
        to_bind: {use_keys: {param: ids}}
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    bind: {use_keys: {param: ids}}
    fields:
      customer_name:
        field: customer_name
        relation: *r1
"""
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        source_bind = config.sources["customers"].bind
        assert source_bind is not None
        assert source_bind.use_keys is not None
        assert source_bind.use_keys.as_ == "set"

        step_bind = config.relations["r1"].steps[0].to_bind
        assert step_bind is not None
        assert step_bind.use_keys is not None
        assert step_bind.use_keys.as_ == "set"

    def test_bind_rows_defaults_to_batch_cache(self) -> None:
        yaml_content = """
name: test_bind_rows_defaults
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      field: order_id
    customer_id:
      field: customer_id
relations:
  r1: &r1
    steps:
      - from: orders.customer_id
        to: customers.customer_id
        to_bind: {use_rows: {param: rows}}
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    bind: {use_rows: {param: rows}}
    fields:
      customer_name:
        field: customer_name
        relation: *r1
"""
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        source_bind = config.sources["customers"].bind
        assert source_bind is not None
        assert source_bind.use_rows is not None
        assert source_bind.use_rows.cache_mode == "batch"

        step_bind = config.relations["r1"].steps[0].to_bind
        assert step_bind is not None
        assert step_bind.use_rows is not None
        assert step_bind.use_rows.cache_mode == "batch"


class TestAllowlistRequired:
    def test_run_requires_allowlist(self, tmp_path: Path) -> None:
        yaml_path = _write_simple_yaml(tmp_path, "test.loader")
        with pytest.raises(AllowlistRequiredError, match="Allowlist is required"):
            run(str(yaml_path), allowed_modules=frozenset())

    def test_converter_requires_allowlist_by_default(self) -> None:
        with pytest.raises(AllowlistRequiredError, match="Allowlist is required"):
            _ = ConfigToIRConverter()

    def test_converter_rejects_resolver_without_allowlist(self) -> None:
        from scalim.dsl.by_yaml.runtime.references import SecurePythonReferenceResolver

        with pytest.raises(AllowlistRequiredError, match="Allowlist is required"):
            _ = ConfigToIRConverter(resolver=SecurePythonReferenceResolver())

    def test_converter_from_allowlist_requires_non_empty_allowlist(self) -> None:
        with pytest.raises(AllowlistRequiredError, match="Allowlist is required"):
            _ = ConfigToIRConverter.from_allowlist()
        with pytest.raises(AllowlistRequiredError, match="Allowlist is required"):
            _ = ConfigToIRConverter.from_allowlist(allowed_modules=frozenset())

    def test_converter_from_allowlist_builds_converter(self) -> None:
        yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      field: order_id
sources: {}
"""
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)
        converter = ConfigToIRConverter.from_allowlist(allowed_modules=frozenset(["tests.conftest"]))
        demand_ir = converter.convert(config)
        assert demand_ir.main_source.source_id == "orders"

    @pytest.mark.parametrize(
        "allow_kwargs",
        [
            {"allowed_modules": frozenset(["tests.conftest"])},
            {"allowed_modules": frozenset(), "allowed_functions": frozenset(["tests.conftest.mock_loader"])},
        ],
        ids=["modules", "functions"],
    )
    def test_run_with_allowlist_passes_check(self, tmp_path: Path, allow_kwargs: dict) -> None:
        yaml_path = _write_simple_yaml(tmp_path, "tests.conftest.mock_loader")
        result = run(str(yaml_path), **allow_kwargs)
        assert result.total_rows == 0


class TestDslVersionRemoved:
    def test_schema_omits_dsl_version(self) -> None:
        schema = build_demand_schema()
        properties = schema.get("properties", {})
        assert "dsl_version" not in properties


class TestIncludeHeader:
    @pytest.mark.parametrize(
        "include_header,expected_lines",
        [
            (True, ["id,name", "1,Alice"]),
            (False, ["1,Alice"]),
        ],
    )
    def test_csv_sink_include_header(self, tmp_path: Path, include_header: bool, expected_lines: List[str]) -> None:
        output_path = tmp_path / ("with_header.csv" if include_header else "no_header.csv")
        sink = CSVSink(str(output_path), field_names=["id", "name"], include_header=include_header)
        sink.write_row({"id": 1, "name": "Alice"})
        sink.close()

        lines = output_path.read_text(encoding="utf-8").strip().splitlines()
        assert lines == expected_lines

    @pytest.mark.parametrize(
        "include_header,expected_lines",
        [
            (True, ["id,name", "1,Alice"]),
            (False, ["1,Alice"]),
        ],
    )
    def test_column_csv_sink_include_header(self, tmp_path: Path, include_header: bool, expected_lines: List[str]) -> None:
        output_path = tmp_path / ("column_with_header.csv" if include_header else "column_no_header.csv")
        sink = ColumnCSVSink(str(output_path), ["id", "name"], include_header=include_header)
        sink.set_row_ids([1])
        sink.write_column("id", {1: 1})
        sink.write_column("name", {1: "Alice"})
        sink.close()

        lines = output_path.read_text(encoding="utf-8").strip().splitlines()
        assert lines == expected_lines


class TestExcelIncludeHeader:
    @pytest.fixture
    def openpyxl(self):
        openpyxl = pytest.importorskip("openpyxl")
        return openpyxl

    @pytest.mark.parametrize(
        "include_header,expected_rows",
        [
            (True, [("id", "name"), (1, "Alice")]),
            (False, [(1, "Alice")]),
        ],
    )
    def test_excel_sink_include_header(self, tmp_path: Path, openpyxl, include_header: bool, expected_rows: List[tuple]) -> None:
        from scalim.sinks.sink_excel import ExcelSink

        output_path = tmp_path / ("with_header.xlsx" if include_header else "no_header.xlsx")
        sink = ExcelSink(str(output_path), field_names=["id", "name"], include_header=include_header)
        sink.write_row({"id": 1, "name": "Alice"})
        sink.close()

        wb = openpyxl.load_workbook(str(output_path))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        assert rows == expected_rows

    @pytest.mark.parametrize(
        "include_header,expected_rows",
        [
            (True, [("id", "name"), (1, "Alice")]),
            (False, [(1, "Alice")]),
        ],
    )
    def test_column_excel_sink_include_header(self, tmp_path: Path, openpyxl, include_header: bool, expected_rows: List[tuple]) -> None:
        from scalim.sinks.sink_excel import ColumnExcelSink

        output_path = tmp_path / ("column_with_header.xlsx" if include_header else "column_no_header.xlsx")
        sink = ColumnExcelSink(str(output_path), field_names=["id", "name"], include_header=include_header)
        sink.set_row_ids([1])
        sink.write_column("id", {1: 1})
        sink.write_column("name", {1: "Alice"})
        sink.close()

        wb = openpyxl.load_workbook(str(output_path))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        assert rows == expected_rows


class TestBindConfigErrors:
    def test_create_params_builder_requires_use_branch(self) -> None:
        converter = ConfigToIRConverter(allow_unsafe_resolver=True)
        bind_config = BindConfig()

        with pytest.raises(ConversionError, match="BindConfig requires use_rows or use_keys"):
            converter._create_params_builder(bind_config)

    def test_create_binding_requires_use_branch(self) -> None:
        converter = ConfigToIRConverter(allow_unsafe_resolver=True)
        bind_config = BindConfig()

        with pytest.raises(ConversionError, match="BindConfig requires use_rows or use_keys"):
            converter._create_binding(bind_config, None, "id")


class TestSchemaItemsChoicesEnum:
    def test_schema_performance_metrics_has_items_enum(self) -> None:
        schema = build_demand_schema()
        definitions = schema["definitions"]
        performance_def = definitions["performance"]
        metrics_schema = performance_def["properties"]["metrics"]

        assert "items" in metrics_schema
        assert "enum" in metrics_schema["items"]
        assert set(metrics_schema["items"]["enum"]) == {"duration", "memory", "cpu"}
