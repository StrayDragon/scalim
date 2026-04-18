import marimo

import csv
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
from scalim.dsl.yaml_dsl import run as run_yaml
from scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario import GuardrailCaptureObserver
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_guardrails_compute_on_error"
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


def _guardrail_codes(components: Optional[Sequence[object]]) -> List[str]:
    codes: List[str] = []
    for c in components or ():
        if isinstance(c, GuardrailCaptureObserver):
            codes.extend([s.code for s in c.signals if s.code])
    return sorted(set(codes))


def run_yaml_dsl_guardrails_compute_on_error(*, yaml_path: Optional[Path] = None) -> ExampleResult:
    if yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_guardrails_compute_on_error.yaml"

    guardrail_capture = GuardrailCaptureObserver()
    with tempfile.TemporaryDirectory(prefix="scalim-guardrails-compute-") as tmpdir:
        tmp = Path(tmpdir)
        out_root_detail = tmp / "out_detail"

        init_vars: Dict[str, object] = {"out_path_detail": str(out_root_detail)}
        from scalim.execution.guardrails import GuardrailsComputePolicy, GuardrailsPolicy

        guardrails = GuardrailsPolicy(
            enabled=True,
            mode="fast_fail",
            compute=GuardrailsComputePolicy(on_error="quiet"),
        )
        try:
            result = run_yaml(
                str(yaml_path),
                options=DemandRunOptions(
                    security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    template=DemandRunTemplateOptions(init_vars=init_vars),
                    runtime=DemandRunRuntimeOptions(
                        components=[guardrail_capture],
                        batch_size=2,
                        guardrails=guardrails,
                    ),
                ),
            )
            core = result.core
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="compile/run failed: {}: {}".format(type(exc).__name__, exc),
                details={"exc_type": type(exc).__name__, "message": str(exc)},
            )

        detail_csv_path = Path(str((core.outputs or {}).get("detail") or ""))
        rows = _read_csv_rows(detail_csv_path) if detail_csv_path.exists() else []
        codes = _guardrail_codes([guardrail_capture])
        has_compute_error = "compute_error" in set(codes)

        # 对拍: ticket_id=1001 必然触发除零 -> risky_score 为空;其余至少一个非空.
        by_id = {r.get("ticket_id") or "": r for r in rows}
        r_1001 = by_id.get("1001") or {}
        blank_for_1001 = (r_1001.get("risky_score") or "") == ""
        any_non_blank = any((r.get("risky_score") or "") != "" for r in rows if (r.get("ticket_id") or "") != "1001")

        passed = bool(len(rows) == 5 and has_compute_error and blank_for_1001 and any_non_blank and core.outputs)
        summary = "rows={} compute_error={} blank_1001={} any_non_blank={} outputs={}".format(
            len(rows),
            has_compute_error,
            blank_for_1001,
            any_non_blank,
            sorted(core.outputs.keys()) if core.outputs else None,
        )

        details: Dict[str, Any] = {
            "yaml_path": str(yaml_path),
            "out_root_detail": str(out_root_detail),
            "detail_csv": str(detail_csv_path),
            "rows": len(rows),
            "guardrail_codes": codes,
            "row_1001": r_1001,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_guardrails_compute_on_error()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_guardrails_compute_on_error

        ## 背景

        工程同学在 YAML 里写 `compute` 时,最常见的风险不是“算错”,而是“算崩”：
        - 分母为 0
        - 上游字段偶发缺失/类型异常
        - 规则迭代引入边界遗漏

        如果每次都要改 Python 才能兜底,维护成本会迅速上升。

        ## 需求方提问（自然语言）

        维护者：能不能在不改代码的情况下,让 compute 的异常既 **不阻断主流程**,又能在 CI 里稳定暴露？

        ## 方案选择（取舍）

        - 全局 `GuardrailsPolicy(mode='quiet')`：简单,但会把其他错误也放过(不够严格)
        - **本章**：全局保持 `fast_fail`,仅对 `compute` 这一类错误放宽:
          - `GuardrailsComputePolicy(on_error='quiet')` -> compute 失败写 `None` 并记录 `compute_error` guardrail

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/support/support_guardrails_compute_on_error.yaml`
        - 断言:
          - 输出行数仍为 5
          - ticket_id=1001 的 risky_score 为空(除零触发)
          - guardrail codes 包含 `compute_error`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch110_yaml_dsl_guardrails_compute_on_error.py::run_yaml_dsl_guardrails_compute_on_error`
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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_guardrails_compute_on_error.yaml"
    return demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Guardrails compute YAML (head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_path, max_lines=140)))
    return (excerpt_head,)


@app.cell
def _(yaml_path):
    result = run_yaml_dsl_guardrails_compute_on_error(yaml_path=yaml_path)
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
