"""c40: YAML→Python runtime policy boundary (lookup_chunking / SourceCache / RowsReuse / RunOverrides defaults)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    LookupChunking,
    RowsReuse,
    RunOverrides,
    SourceCache,
    compile,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.typedefs import SourceSpecIrCacheMode

_ALLOWED = frozenset(["tests.fixtures"])


def _security() -> DemandRunSecurityOptions:
    return DemandRunSecurityOptions(allowed_modules=_ALLOWED)


def _minimal_demand_yaml(
    *,
    customers_extra: str = "",
    customers_params: str = "",
) -> str:
    params_block = ""
    if customers_params:
        params_block = "\n    params:\n{}".format(customers_params)
    extra = ""
    if customers_extra:
        extra = "\n{}".format(customers_extra)
    return """
name: demo
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
    key: customer_id{extra}{params_block}
    fields:
      customer_name:
        extract: customer_name
        relation: *r1
""".format(extra=extra, params_block=params_block).lstrip()


def test_yaml_lookup_chunk_size_rejected_with_lookup_chunking_hint(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        _minimal_demand_yaml(customers_extra="    lookup_chunk_size: 10"),
        encoding="utf-8",
    )

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = YamlDemandLoader().load(yaml_path)

    msg = "\n".join(env.message for env in excinfo.value.errors)
    assert "lookup_chunk_size" in msg
    assert "LookupChunking" in msg


def test_yaml_output_write_layout_rejected_with_python_hint(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    body = _minimal_demand_yaml() + "\noutput_write_layout: column_chunked\n"
    yaml_path.write_text(body, encoding="utf-8")

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = YamlDemandLoader().load(yaml_path)

    msg = "\n".join(env.message for env in excinfo.value.errors)
    assert "output_write_layout" in msg
    assert "OutputWriteLayout" in msg
    assert any(env.path == "output_write_layout" for env in excinfo.value.errors)


def test_yaml_excel_column_residency_rejected_with_python_hint(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    body = _minimal_demand_yaml() + "\nexcel_column_residency: chunked\n"
    yaml_path.write_text(body, encoding="utf-8")

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = YamlDemandLoader().load(yaml_path)

    msg = "\n".join(env.message for env in excinfo.value.errors)
    assert "excel_column_residency" in msg
    assert "OutputWriteLayout" in msg
    assert "COLUMN_CHUNKED" in msg
    assert any(env.path == "excel_column_residency" for env in excinfo.value.errors)


def test_compile_lookup_chunking_sized_applies_source_ir_chunk_size(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(_minimal_demand_yaml(), encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=_security(),
            runtime=DemandRunRuntimeOptions(
                lookup_chunking={"customers": LookupChunking.sized(10)},
            ),
        ),
    )

    source = compilation.demand_ir.sources["customers"]
    assert source.lookup_chunk_size == 10
    assert source.lookup_chunk_parallel is False


def test_source_cache_python_override_beats_yaml_cache_mode(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        _minimal_demand_yaml(customers_extra="    cache_mode: preload_forever"),
        encoding="utf-8",
    )

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=_security(),
            runtime=DemandRunRuntimeOptions(
                source_cache={"customers": SourceCache.none()},
            ),
        ),
    )

    assert compilation.config.sources["customers"].cache_mode == "preload_forever"
    assert compilation.demand_ir.sources["customers"].cache_mode == SourceSpecIrCacheMode.NONE


def test_rows_reuse_python_override_beats_yaml_rows_cache_mode(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        _minimal_demand_yaml(
            customers_params="      rows:\n        $rows:\n          cache_mode: batch",
        ),
        encoding="utf-8",
    )

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=_security(),
            runtime=DemandRunRuntimeOptions(
                rows_reuse={"customers": RowsReuse.none()},
            ),
        ),
    )

    binding = compilation.demand_ir.sources["customers"].bind
    assert binding is not None
    assert binding.mode == "rows"
    assert binding.cache_mode == "none"


def test_compile_without_lookup_chunking_leaves_source_unchunked(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(_minimal_demand_yaml(), encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(security=_security()),
    )

    source = compilation.demand_ir.sources["customers"]
    assert source.lookup_chunk_size is None
    assert source.lookup_chunk_parallel is None
    assert compilation.request.parallelize_lookup_chunks is False


def test_run_overrides_csv_write_header_defaults_when_fields_only(tmp_path: Path) -> None:
    overrides = RunOverrides.csv_file(output_root=tmp_path / "csv", fields=("order_id",))
    assert overrides.outputs is not None
    write = overrides.outputs[0].write
    assert write is not None
    assert write.include_header is True
    assert write.header_fields_output_by == "name"


def test_run_overrides_csv_and_xlsx_default_header_fields_output_by_name(tmp_path: Path) -> None:
    csv = RunOverrides.csv_file(output_root=tmp_path / "csv", fields=("order_id",))
    assert csv.outputs is not None
    assert len(csv.outputs) == 1
    assert csv.outputs[0].write is not None
    assert csv.outputs[0].write.header_fields_output_by == "name"

    xlsx = RunOverrides.xlsx_file_single_sheet(
        output_root=tmp_path / "xlsx",
        fields=("order_id",),
        sheet="Detail",
    )
    assert xlsx.outputs is not None
    assert len(xlsx.outputs) == 1
    assert xlsx.outputs[0].write is not None
    assert xlsx.outputs[0].write.header_fields_output_by == "name"


def test_run_overrides_csv_file_encoding_default_is_utf8(tmp_path: Path) -> None:
    overrides = RunOverrides.csv_file(output_root=tmp_path / "csv", fields=("order_id",))
    assert overrides.resources is not None
    assert overrides.resources.files is not None
    file_override = overrides.resources.files["detail_csv"]
    assert file_override.encoding == "utf-8"


def test_yaml_csv_file_omitted_encoding_defaults_utf8() -> None:
    config = YamlDemandLoader().load_string(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv: {csv_file: {path: ./out}}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [order_id]
""".lstrip()
    )
    assert config.resources is not None
    assert config.resources.files["detail_csv"].encoding == "utf-8"


def test_source_cache_python_preload_beats_yaml_none(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        _minimal_demand_yaml(customers_extra="    cache_mode: none"),
        encoding="utf-8",
    )

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=_security(),
            runtime=DemandRunRuntimeOptions(
                source_cache={"customers": SourceCache.preload_forever()},
            ),
        ),
    )

    assert compilation.config.sources["customers"].cache_mode == "none"
    assert compilation.demand_ir.sources["customers"].cache_mode == SourceSpecIrCacheMode.PRELOAD_FOREVER


def test_rows_reuse_python_batch_beats_yaml_none(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        _minimal_demand_yaml(
            customers_params="      rows:\n        $rows:\n          cache_mode: none",
        ),
        encoding="utf-8",
    )

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=_security(),
            runtime=DemandRunRuntimeOptions(
                rows_reuse={"customers": RowsReuse.batch()},
            ),
        ),
    )

    binding = compilation.demand_ir.sources["customers"].bind
    assert binding is not None
    assert binding.mode == "rows"
    assert binding.cache_mode == "batch"


def test_lookup_chunking_sized_parallel_sets_source_and_request_parallel(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(_minimal_demand_yaml(), encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=_security(),
            runtime=DemandRunRuntimeOptions(
                parallel_mode="adaptive",
                max_workers=3,
                lookup_chunking={"customers": LookupChunking.sized(5, parallel=True)},
            ),
        ),
    )

    source = compilation.demand_ir.sources["customers"]
    assert source.lookup_chunk_size == 5
    assert source.lookup_chunk_parallel is True
    assert compilation.request.parallelize_lookup_chunks is True


def test_lookup_chunking_post_init_rejects_invalid_max_chunk_workers() -> None:
    with pytest.raises(ValueError, match="max_chunk_workers"):
        _ = LookupChunking(size=2, parallel=False, max_chunk_workers=0, _kind="sized")
    with pytest.raises(TypeError, match="max_chunk_workers"):
        _ = LookupChunking(size=2, parallel=False, max_chunk_workers=True, _kind="sized")  # type: ignore[arg-type]
