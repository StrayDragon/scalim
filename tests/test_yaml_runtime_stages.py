from pathlib import Path

import pytest

from scalim.dsl.by_yaml.runtime.contracts import RunOptions
from scalim.dsl.by_yaml.runtime.errors import ScalimAllowlistRequiredError
from scalim.dsl.by_yaml.runtime.stages import (
    ScalimStageAllowlistMismatchError,
    stage_create_context,
    stage_compile_demand_ir,
    stage_build_execution_request,
    stage_load_yaml_config,
    stage_validate_allowlist,
)


def _write_yaml(tmp_path: Path) -> str:
    yaml_path = tmp_path / "stages.yaml"
    yaml_path.write_text(
        """
name: stages
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
        encoding="utf-8",
    )
    return str(yaml_path)


def test_stage_validate_allowlist_requires_non_empty_allowlist() -> None:
    with pytest.raises(ScalimAllowlistRequiredError, match="Allowlist is required"):
        stage_validate_allowlist(allowed_modules=frozenset(), allowed_functions=None)


def test_stage_parse_convert_and_map_request(tmp_path: Path) -> None:
    yaml_path = _write_yaml(tmp_path)

    context = stage_create_context(allowed_modules=frozenset(["tests.conftest"]), allowed_functions=None)
    config = stage_load_yaml_config(yaml_path)

    demand_ir = stage_compile_demand_ir(config, context=context)

    options = RunOptions(allowed_modules=frozenset(["tests.conftest"]))
    request = stage_build_execution_request(config, demand_ir, options=options, context=context)

    assert config.name == "stages"
    assert demand_ir.main_source.source_id == "orders"
    assert tuple(request.export_layout.field_ids) == ("order_id",)


def test_stage_map_request_rejects_allowlist_mismatch(tmp_path: Path) -> None:
    yaml_path = _write_yaml(tmp_path)
    context = stage_create_context(allowed_modules=frozenset(["tests.conftest"]), allowed_functions=None)
    config = stage_load_yaml_config(yaml_path)
    demand_ir = stage_compile_demand_ir(config, context=context)

    options = RunOptions(allowed_modules=frozenset(["tests.other"]))
    with pytest.raises(ScalimStageAllowlistMismatchError, match=ScalimStageAllowlistMismatchError.MESSAGE):
        _ = stage_build_execution_request(config, demand_ir, options=options, context=context)
