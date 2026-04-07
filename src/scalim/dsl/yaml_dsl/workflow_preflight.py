"""`workflow` 预检查(`preflight`)(内部模块).

目标:
- 在 `workflow` 引擎启动前运行一组“运行期但可推理”的诊断
- 快速失败:发现第一个错误立即抛出,并中止整个 `workflow`

约束:
- 运行时需兼容 `Python 3.6`
- 必须基于每个 `run` 的有效运行期策略/覆盖项(由调用侧准备好 `RunOptions`)进行判断
"""

from typing import Dict, List, Sequence, Tuple

from ...vendor.compact.typing_extensionsx import Protocol
from ...vendor.dataclassesx import dataclass
from .diagnostics import format_duplicate_effective_field_display_names_message
from .runtime.contracts import RunOptions
from .runtime.effective_outputs import options_require_unique_effective_field_display_names
from .schema_dsl.models import DemandConfig
from .workflow import ScalimWorkflowConfigError


@dataclass(frozen=True)
class WorkflowPreflightContext:
    workflow_yaml_path: str


@dataclass(frozen=True)
class WorkflowPreflightRun:
    run_id: str
    demand_path: str
    decl_order: int
    demand_config: DemandConfig
    options: RunOptions


class WorkflowPreflightCheck(Protocol):
    check_id: str

    def run(self, ctx: WorkflowPreflightContext, run: WorkflowPreflightRun) -> None: ...


def run_workflow_preflight(
    ctx: WorkflowPreflightContext,
    *,
    runs: Sequence[WorkflowPreflightRun],
    checks: Sequence[WorkflowPreflightCheck],
) -> None:
    ordered = sorted(runs, key=lambda r: int(r.decl_order))
    for run in ordered:
        for check in checks:
            check.run(ctx, run)


def _collect_duplicate_effective_field_display_names(config: DemandConfig) -> Dict[str, List[str]]:
    conflicts: Dict[str, List[str]] = {}

    for field_id, field_cfg in config.source_fields.items():
        name = str(field_cfg.name or "").strip()
        effective = name or str(field_id)
        conflicts.setdefault(effective, []).append(str(field_id))

    for field_id, field_cfg in config.derived_fields.items():
        name = str(field_cfg.name or "").strip()
        effective = name or str(field_id)
        conflicts.setdefault(effective, []).append(str(field_id))

    return {name: ids for name, ids in conflicts.items() if len(ids) > 1}


class ValidateUniqueFieldNamesPreflightCheck:
    check_id: str = "validate_unique_field_names"

    def run(self, ctx: WorkflowPreflightContext, run: WorkflowPreflightRun) -> None:
        _ = ctx

        demand_diagnostics = run.options.demand_diagnostics
        validate_unique = True if demand_diagnostics is None else bool(demand_diagnostics.validate_unique_field_names)
        if not validate_unique:
            return

        config = run.demand_config
        if not options_require_unique_effective_field_display_names(config, options=run.options):
            return

        duplicates = _collect_duplicate_effective_field_display_names(config)
        if not duplicates:
            return

        msg = format_duplicate_effective_field_display_names_message(duplicates)
        full = "Workflow preflight failed: run_id={!r}, demand_path={!r}: {}".format(str(run.run_id), str(run.demand_path), msg)
        path = "workflow.runs.{}.demand".format(int(run.decl_order))
        raise ScalimWorkflowConfigError(full, path=path)


WORKFLOW_PREFLIGHT_CHECKS: Tuple[WorkflowPreflightCheck, ...] = (ValidateUniqueFieldNamesPreflightCheck(),)


__all__ = (
    "WORKFLOW_PREFLIGHT_CHECKS",
    "WorkflowPreflightCheck",
    "WorkflowPreflightContext",
    "WorkflowPreflightRun",
    "run_workflow_preflight",
)
