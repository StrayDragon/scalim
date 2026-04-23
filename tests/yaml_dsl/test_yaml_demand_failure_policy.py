from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, compile
from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError

_ALLOWED_MODULES = frozenset(["tests.fixtures.mock_loaders"])


def test_yaml_failure_policy_is_rejected_with_migration_guidance(tmp_path: Path) -> None:
    yaml_text = """
name: demo
failure_policy: primary_only
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""".lstrip()

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(str(yaml_path), options=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES)))

    assert any(env.path == "failure_policy" for env in excinfo.value.errors)


def test_runtime_demand_failure_policy_override_is_applied(tmp_path: Path) -> None:
    yaml_text = """
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

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
            runtime=DemandRunRuntimeOptions(demand_failure_policy="primary_only"),
        ),
    )

    assert compilation.config.failure_policy == "primary_only"
    assert compilation.request.output_composition is not None
    assert compilation.request.output_composition.failure_policy == "primary_only"


def test_invalid_runtime_demand_failure_policy_is_rejected(tmp_path: Path) -> None:
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""".lstrip()

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValueError, match="expected one of"):
        _ = compile(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                runtime=DemandRunRuntimeOptions(demand_failure_policy="nope"),
            ),
        )
