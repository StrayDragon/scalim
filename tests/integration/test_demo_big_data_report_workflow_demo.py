import os
from pathlib import Path

from scalim.dsl.by_yaml import run_workflow
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import (
    get_config,
    get_workflow_preload_counter_calls,
    reset_workflow_preload_counter_calls,
    set_config,
)
from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL
from scalim_misc.demo_big_data_report.verification import verify_scalim_output_csv
from tests.support.pathing import repo_root as _repo_root


def test_demo_big_data_report_workflow_demo_smoke(tmp_path: Path) -> None:
    repo_root = _repo_root()
    workflow_yaml_path = repo_root / "notebooks" / "marimo" / "demo_big_data_report" / "by_yaml_dsl" / "workflow_demo_big_data_report.yaml"

    cfg = build_test_config_small()
    prev = get_config()
    set_config(cfg)
    try:
        reset_workflow_preload_counter_calls()
        wf_copy = tmp_path / "workflow.yaml"
        wf_copy.write_text(workflow_yaml_path.read_text(encoding="utf-8"), encoding="utf-8")

        prev_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            result = run_workflow(
                str(wf_copy),
                allowed_modules=frozenset(["scalim_misc.demo_big_data_report.loaders", "scalim.workflow.loaders"]),
                init_vars={"order_ids": []},
                path_aliases={"@": str(repo_root)},
                allowed_yaml_roots=(str(repo_root),),
            )
        finally:
            os.chdir(prev_cwd)

        assert not result.errors()
        assert get_workflow_preload_counter_calls() == 1

        detail_csv = tmp_path / "detail.csv"
        metrics_csv = tmp_path / "metrics.csv"
        report_xlsx = tmp_path / "report.xlsx"
        assert detail_csv.exists()
        assert metrics_csv.exists()
        assert report_xlsx.exists()

        verification = verify_scalim_output_csv(detail_csv, fields_to_check=TARGET_FIELDS_FULL)
        assert verification.passed, verification.summary
        assert verification.checked_rows == verification.total_rows
    finally:
        set_config(prev)
