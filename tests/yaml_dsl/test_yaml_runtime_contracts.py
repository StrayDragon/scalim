import json
from pathlib import Path
from typing import List

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    ResolverTrustedMode,
    run,
)
from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
from scalim.dsl.yaml_dsl.runtime.errors import ScalimAllowlistRequiredError
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


def _load_demand_schema() -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "src" / "scalim" / "dsl" / "yaml_dsl" / "schema" / "demand.gen.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


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
        lookup_cast: {sep_first: {sep: ","}}
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
        converter = ConfigToIRConverter()
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
        converter = ConfigToIRConverter()
        demand_ir = converter.convert(config)
        binding = demand_ir.sources["customers"].bind
        assert binding is not None
        assert binding.mode == "rows"
        assert binding.cache_mode == "batch"


class TestAllowlistRequired:
    def test_run_requires_allowlist(self, tmp_path: Path) -> None:
        yaml_path = _write_simple_yaml(tmp_path, "test.loader")
        with pytest.raises(ScalimAllowlistRequiredError, match="Allowlist is required"):
            run(str(yaml_path), options=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset())))

    def test_converter_does_not_require_allowlist(self) -> None:
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
        converter = ConfigToIRConverter()
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
        options = DemandRunOptions(security=DemandRunSecurityOptions(**allow_kwargs))
        result = run(str(yaml_path), options=options)
        assert result.total_rows == 0


class TestDslVersionRemoved:
    def test_schema_omits_dsl_version(self) -> None:
        schema = _load_demand_schema()
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


class TestDemandRunOptionsContractsCoverage:
    def test_coerce_iterable_str_helpers_cover_error_branches(self) -> None:
        import scalim.dsl.yaml_dsl.runtime.contracts as contracts_mod

        with pytest.raises(TypeError, match=r"iterable of str"):
            _ = contracts_mod._coerce_iterable_str_frozenset(None, field_name="x")  # noqa: SLF001
        with pytest.raises(TypeError, match=r"not a str"):
            _ = contracts_mod._coerce_iterable_str_frozenset("abc", field_name="x")  # noqa: SLF001
        with pytest.raises(TypeError, match=r"iterable of str"):
            _ = contracts_mod._coerce_iterable_str_frozenset(123, field_name="x")  # noqa: SLF001

        with pytest.raises(TypeError, match=r"iterable of str"):
            _ = contracts_mod._coerce_iterable_str_tuple(None, field_name="x")  # noqa: SLF001
        with pytest.raises(TypeError, match=r"not a str"):
            _ = contracts_mod._coerce_iterable_str_tuple("abc", field_name="x")  # noqa: SLF001
        with pytest.raises(TypeError, match=r"iterable of str"):
            _ = contracts_mod._coerce_iterable_str_tuple(123, field_name="x")  # noqa: SLF001

    def test_security_options_normalizes_str_enum_and_rejects_bad_mode_type(self) -> None:
        security = DemandRunSecurityOptions(
            allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
            resolver_trusted_mode="strict_allowlist",  # type: ignore[arg-type] contract normalization boundary
        )
        assert security.resolver_trusted_mode == ResolverTrustedMode.STRICT_ALLOWLIST

        with pytest.raises(TypeError, match=r"resolver_trusted_mode"):
            _ = DemandRunSecurityOptions(
                allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
                resolver_trusted_mode=1,  # type: ignore[arg-type] contract validation boundary
            )

    def test_security_options_normalizes_public_builtin_callable_ids(self) -> None:
        security = DemandRunSecurityOptions(
            allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
            public_builtin_callable_ids=["foo"],  # type: ignore[arg-type] contract normalization boundary
        )
        assert security.public_builtin_callable_ids == ("foo",)

    def test_template_options_rendered_yaml_max_len_validation_cover_branches(self) -> None:
        with pytest.raises(TypeError, match=r"rendered_yaml_max_len"):
            _ = DemandRunTemplateOptions(rendered_yaml_max_len=True)

        with pytest.raises(ValueError, match=r"rendered_yaml_max_len"):
            _ = DemandRunTemplateOptions(rendered_yaml_max_len=0)

    def test_runtime_options_parallel_mode_and_max_workers_validation_cover_branches(self) -> None:
        with pytest.raises(ValueError, match=r"parallel_mode"):
            _ = DemandRunRuntimeOptions(parallel_mode="nope")  # type: ignore[arg-type] contract validation boundary

        with pytest.raises(TypeError, match=r"max_workers"):
            _ = DemandRunRuntimeOptions(max_workers=True)

        with pytest.raises(ValueError, match=r"max_workers"):
            _ = DemandRunRuntimeOptions(max_workers=-1)

    def test_runtime_options_chunk_parallelism_validation_cover_branches(self) -> None:
        with pytest.raises(TypeError, match=r"parallelize_lookup_chunks must be a boolean"):
            _ = DemandRunRuntimeOptions(parallelize_lookup_chunks="yes")  # type: ignore[arg-type] contract validation boundary

        with pytest.raises(TypeError, match=r"max_chunk_workers must be an int"):
            _ = DemandRunRuntimeOptions(max_chunk_workers=True)  # type: ignore[arg-type] contract validation boundary

        with pytest.raises(ValueError, match=r"max_chunk_workers must be >= 1"):
            _ = DemandRunRuntimeOptions(max_chunk_workers=0)

        options = DemandRunRuntimeOptions(parallel_mode="adaptive", parallelize_lookup_chunks=True, max_chunk_workers=2)
        assert options.parallelize_lookup_chunks is True
        assert options.max_chunk_workers == 2

    def test_output_options_capture_validation_cover_branch(self) -> None:
        with pytest.raises(TypeError, match=r"capture"):
            _ = DemandRunOutputOptions(capture="nope")  # type: ignore[arg-type] contract validation boundary

    def test_demand_run_options_type_checks_cover_branches(self) -> None:
        security = DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))

        with pytest.raises(TypeError, match=r"DemandRunOptions.security must be a DemandRunSecurityOptions"):
            _ = DemandRunOptions(security="nope")  # type: ignore[arg-type] contract validation boundary

        with pytest.raises(TypeError, match=r"DemandRunOptions.template must be a DemandRunTemplateOptions"):
            _ = DemandRunOptions(security=security, template="nope")  # type: ignore[arg-type] contract validation boundary

        with pytest.raises(TypeError, match=r"DemandRunOptions.runtime must be a DemandRunRuntimeOptions"):
            _ = DemandRunOptions(security=security, runtime="nope")  # type: ignore[arg-type] contract validation boundary

        with pytest.raises(TypeError, match=r"DemandRunOptions.outputs must be a DemandRunOutputOptions"):
            _ = DemandRunOptions(security=security, outputs="nope")  # type: ignore[arg-type] contract validation boundary

        with pytest.raises(TypeError, match=r"DemandRunOptions.resources_policy must be a ResourcesPolicy or None"):
            _ = DemandRunOptions(security=security, resources_policy="nope")  # type: ignore[arg-type] contract validation boundary

    def test_normalize_public_demand_run_options_replaces_when_template_sandbox_needs_trimming(self) -> None:
        from scalim.dsl.yaml_dsl.runtime.normalize import normalize_public_demand_run_options

        options = DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"])))
        object.__setattr__(options.template, "template_sandbox", " safe ")

        normalized = normalize_public_demand_run_options(options)
        assert normalized is not options
        assert normalized.template.template_sandbox == "safe"

    def test_apply_demand_runtime_policy_overrides_rejects_invalid_batch_size_values_cover_branches(self) -> None:
        from scalim.dsl.yaml_dsl.runtime import compiler as compiler_mod
        from scalim.dsl.yaml_dsl.schema_dsl.models import DemandConfig

        options = DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"])))

        object.__setattr__(options.runtime, "batch_size", "nope")
        with pytest.raises(TypeError, match=r"batch_size must be an integer"):
            _ = compiler_mod._apply_demand_runtime_policy_overrides(  # noqa: SLF001
                DemandConfig(),
                options=options,
            )

        object.__setattr__(options.runtime, "batch_size", 0)
        with pytest.raises(ValueError, match=r"batch_size must be >= 1"):
            _ = compiler_mod._apply_demand_runtime_policy_overrides(  # noqa: SLF001
                DemandConfig(),
                options=options,
            )


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
        schema = _load_demand_schema()
        definitions = schema["definitions"]

        assert "observability" not in schema["properties"]
        for legacy in ("logging", "performance", "relations", "viz", "trace", "row_gap", "memory_opt", "observability"):
            assert legacy not in definitions
