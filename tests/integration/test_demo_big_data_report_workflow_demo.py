from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    WorkflowRunOptions,
    run_workflow,
)
from scalim.dsl.yaml_dsl.workflow_types import WorkflowCachePoolPreloadForeverShared, WorkflowExecutionOptions, WorkflowRuntimeOptions
from scalim.execution import versioned_outputs
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import (
    get_workflow_preload_counter_calls,
    reset_workflow_preload_counter_calls,
)
from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL
from scalim_misc.demo_big_data_report.verification import verify_scalim_output_csv
from scalim_misc.notebook_support.pathing import demo_big_data_report_workflow_demo_yaml_path
from tests.support.demo_big_data_report_config import patched_ecommerce_config
from tests.support.pathing import repo_root as _repo_root


def test_demo_big_data_report_workflow_demo_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo_root()
    workflow_yaml_path = demo_big_data_report_workflow_demo_yaml_path(__file__)

    cfg = build_test_config_small()
    with patched_ecommerce_config(cfg):
        reset_workflow_preload_counter_calls()
        wf_copy = tmp_path / "workflow.yaml"
        wf_copy.write_text(workflow_yaml_path.read_text(encoding="utf-8"), encoding="utf-8")
        for demand_filename in (
            "workflow_demo_big_data_report_detail_demand.yaml",
            "workflow_demo_big_data_report_metrics_demand.yaml",
        ):
            (tmp_path / demand_filename).write_text(
                (workflow_yaml_path.parent / demand_filename).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        monkeypatch.chdir(tmp_path)
        workflow_runtime_options = WorkflowRuntimeOptions(
            execution=WorkflowExecutionOptions(max_concurrency=2, failure_policy="all_fail"),
            cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16),
        )
        demand_options = DemandRunOptions(
            security=DemandRunSecurityOptions(
                allowed_modules=frozenset(["scalim_misc.demo_big_data_report.loaders", "scalim.workflow.loaders"]),
                allowed_yaml_roots=(str(repo_root),),
            ),
            template=DemandRunTemplateOptions(init_vars={"order_ids": []}),
            runtime=DemandRunRuntimeOptions(batch_size=30),
        )
        options = WorkflowRunOptions(
            demand=demand_options,
            runtime=workflow_runtime_options,
            path_aliases={"@": str(repo_root)},
        )
        result = run_workflow(
            str(wf_copy),
            options=options,
        )

        assert not result.errors()
        assert get_workflow_preload_counter_calls() == 1

        out_root = tmp_path / "out"
        latest = versioned_outputs.read_latest(out_root)
        version_id = str(latest["version_id"])
        version_dir = out_root / "versions" / version_id

        detail_csv = version_dir / "files" / "detail_csv.csv"
        metrics_csv = version_dir / "files" / "metrics_csv.csv"
        report_xlsx = version_dir / "books" / "report.xlsx"
        assert detail_csv.exists()
        assert metrics_csv.exists()
        assert report_xlsx.exists()

        verification = verify_scalim_output_csv(detail_csv, fields_to_check=TARGET_FIELDS_FULL)
        assert verification.passed, verification.summary
        assert verification.checked_rows == verification.total_rows
