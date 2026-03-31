import marimo

import csv
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.execution.run_ir import run_ir
from scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario import GuardrailCaptureObserver
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_lookup_cast_sep_first_type_error_guardrail"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
    return rows


def run_yaml_dsl_lookup_cast_sep_first_type_error_guardrail(*, yaml_path: Optional[Path] = None) -> ExampleResult:
    if yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        yaml_path = (
            demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_lookup_cast_sep_first_type_error_guardrail.yaml"
        )

    guardrail_capture = GuardrailCaptureObserver()
    with tempfile.TemporaryDirectory(prefix="scalim-lookup-cast-") as tmpdir:
        tmp = Path(tmpdir)
        out_detail = tmp / "detail.csv"

        init_vars: Dict[str, object] = {"out_path_detail": str(out_detail)}
        try:
            compilation = compile_yaml(
                str(yaml_path),
                allowed_modules=_ALLOWED_MODULES,
                components=[guardrail_capture],
                init_vars=init_vars,
            )
            core = run_ir(compilation.demand_ir, compilation.request)
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="compile/run failed: {}: {}".format(type(exc).__name__, exc),
                details={"exc_type": type(exc).__name__, "message": str(exc)},
            )

        rows = _read_csv_rows(out_detail) if out_detail.exists() else []
        got_codes = {s.code for s in guardrail_capture.signals if s.code}
        has_type_error_guardrail = "relation_type_error_rate_exceeded" in got_codes

        by_ticket = {r.get("ticket_id") or "": r for r in rows}
        ok_2001 = (by_ticket.get("2001") or {}).get("agent_team") == "team-a"
        ok_2002 = (by_ticket.get("2002") or {}).get("agent_team") == ""

        passed = bool(len(rows) == 3 and has_type_error_guardrail and ok_2001 and ok_2002 and core.outputs)
        summary = "rows={} type_error_guardrail={} ok_2001={} ok_2002={} outputs={}".format(
            len(rows),
            has_type_error_guardrail,
            ok_2001,
            ok_2002,
            sorted(core.outputs.keys()) if core.outputs else None,
        )
        details: Dict[str, Any] = {
            "yaml_path": str(yaml_path),
            "detail_csv": str(out_detail),
            "rows": len(rows),
            "guardrail_codes": sorted(got_codes),
            "row_2001": by_ticket.get("2001"),
            "row_2002": by_ticket.get("2002"),
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_lookup_cast_sep_first_type_error_guardrail()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_lookup_cast_sep_first_type_error_guardrail

        ## 背景

        真实业务里,“维表关联不上”经常不是逻辑错,而是 **key 脏**：
        - `"11,legacy"` 这种拼接后缀
        - `""` 这种空字符串(不是 `null`,但同样不可用)

        如果我们把清洗逻辑散落在 Python 里,后续很难在配置审查阶段发现 drift。

        ## 需求方提问（自然语言）

        维护者：我能不能在 YAML 里声明 join key 的清洗,并在出现清洗失败时有确定性信号？

        ## 本章覆盖的 YAML DSL 能力

        - relation step `lookup_cast.sep_first` + `sep`：按分隔符取首段后做 key normalize
        - `guardrails.relations.type_error_max_rate`：把 key 清洗失败(type_error)变成可回归 guardrail

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/support/support_lookup_cast_sep_first_type_error_guardrail.yaml`
        - 断言:
          - ticket_id=2001 关联到 `team-a`
          - ticket_id=2002 为空字符串触发 type_error -> agent_team 为空
          - guardrail codes 包含 `relation_type_error_rate_exceeded`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/12_yaml_dsl_lookup_cast_sep_first_type_error_guardrail.py::run_yaml_dsl_lookup_cast_sep_first_type_error_guardrail`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    demo_dir = Path(__file__).resolve().parents[1]
    yaml_path = (
        demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_lookup_cast_sep_first_type_error_guardrail.yaml"
    )
    return demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## lookup_cast + guardrails demand YAML (head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_path, max_lines=140)))
    return (excerpt_head,)


@app.cell
def _(yaml_path):
    result = run_yaml_dsl_lookup_cast_sep_first_type_error_guardrail(yaml_path=yaml_path)
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
