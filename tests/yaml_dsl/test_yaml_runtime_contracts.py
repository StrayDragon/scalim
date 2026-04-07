from pathlib import Path
from typing import List

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl import RunOptions, run
from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
from scalim.dsl.yaml_dsl.runtime.errors import ScalimAllowlistRequiredError
from scalim.dsl.yaml_dsl.schema_dsl.builder import build_demand_schema
from scalim.sinks import CSVSink, ColumnCSVSink


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
      extract: order_id
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
    customer_id:
      extract: customer_id
relations:
  r1: &r1
    steps:
      - from: orders.customer_id
        to: customers.customer_id
        lookup_cast: {name: sep_first, sep: ","}
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    fields:
      customer_name:
        extract: customer_name
        relation: *r1
"""
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)

        step = config.relations["r1"].steps[0]
        assert step.lookup_cast is not None
        assert step.lookup_cast.name == "sep_first"
        assert step.lookup_cast.sep == ","

    def test_keys_directive_defaults_to_set(self) -> None:
        yaml_content = """
name: test_bind_defaults
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
    customer_id:
      extract: customer_id
relations:
  r1: &r1
    steps:
      - from: orders.customer_id
        to: customers.customer_id
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    params:
      ids:
        $keys: null
    fields:
      customer_name:
        extract: customer_name
        relation: *r1
"""
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)
        converter = ConfigToIRConverter.from_allowlist(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))
        demand_ir = converter.convert(config)
        binding = demand_ir.sources["customers"].bind
        assert binding is not None
        assert binding.mode == "keys"
        assert binding.as_ == "set"

    def test_rows_directive_defaults_to_batch_cache(self) -> None:
        yaml_content = """
name: test_bind_rows_defaults
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
    customer_id:
      extract: customer_id
relations:
  r1: &r1
    steps:
      - from: orders.customer_id
        to: customers.customer_id
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    params:
      rows:
        $rows: null
    fields:
      customer_name:
        extract: customer_name
        relation: *r1
"""
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)
        converter = ConfigToIRConverter.from_allowlist(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))
        demand_ir = converter.convert(config)
        binding = demand_ir.sources["customers"].bind
        assert binding is not None
        assert binding.mode == "rows"
        assert binding.cache_mode == "batch"


class TestAllowlistRequired:
    def test_run_requires_allowlist(self, tmp_path: Path) -> None:
        yaml_path = _write_simple_yaml(tmp_path, "test.loader")
        with pytest.raises(ScalimAllowlistRequiredError, match="Allowlist is required"):
            run(str(yaml_path), options=RunOptions(allowed_modules=frozenset()))

    def test_converter_requires_allowlist_by_default(self) -> None:
        with pytest.raises(ScalimAllowlistRequiredError, match="Allowlist is required"):
            _ = ConfigToIRConverter()

    def test_converter_rejects_resolver_without_allowlist(self) -> None:
        from scalim.dsl.yaml_dsl.runtime.references import SecurePythonReferenceResolver

        with pytest.raises(ScalimAllowlistRequiredError, match="Allowlist is required"):
            _ = ConfigToIRConverter(resolver=SecurePythonReferenceResolver())

    def test_converter_from_allowlist_requires_non_empty_allowlist(self) -> None:
        with pytest.raises(ScalimAllowlistRequiredError, match="Allowlist is required"):
            _ = ConfigToIRConverter.from_allowlist()
        with pytest.raises(ScalimAllowlistRequiredError, match="Allowlist is required"):
            _ = ConfigToIRConverter.from_allowlist(allowed_modules=frozenset())

    def test_converter_from_allowlist_builds_converter(self) -> None:
        yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
"""
        loader = YamlDemandLoader()
        config = loader.load_string(yaml_content)
        converter = ConfigToIRConverter.from_allowlist(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))
        demand_ir = converter.convert(config)
        assert demand_ir.main_source.source_id == "orders"

    @pytest.mark.parametrize(
        "allow_kwargs",
        [
            {"allowed_modules": frozenset(["tests.fixtures.mock_loaders"])},
            {"allowed_modules": frozenset(), "allowed_functions": frozenset(["tests.fixtures.mock_loaders.mock_loader"])},
        ],
        ids=["modules", "functions"],
    )
    def test_run_with_allowlist_passes_check(self, tmp_path: Path, allow_kwargs: dict) -> None:
        yaml_path = _write_simple_yaml(tmp_path, "tests.fixtures.mock_loaders.mock_loader")
        options = RunOptions(**allow_kwargs)
        result = run(str(yaml_path), options=options)
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
        from scalim.sinks import ExcelSink

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
        from scalim.sinks import ColumnExcelSink

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


class TestSchemaObservabilityRemoved:
    def test_schema_has_no_observability_definitions(self) -> None:
        schema = build_demand_schema()
        definitions = schema["definitions"]

        assert "observability" not in schema["properties"]
        for legacy in ("logging", "performance", "relations", "viz", "trace", "row_gap", "memory_opt", "observability"):
            assert legacy not in definitions
