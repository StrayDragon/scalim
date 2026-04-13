"""从异常或成功负载纯函数构建 `WorkflowRunOutcome`(无控制器/执行器实例状态)."""

from typing import List, Optional

from ..exceptions import safe_error_message as _safe_error_message
from ..exceptions import safe_error_type as _safe_error_type
from .report import WorkflowRunError, WorkflowRunOutcome
from .resources import ScalimWorkflowWriteError


def safe_error_type(exc: BaseException) -> str:
    return _safe_error_type(exc)


def safe_error_message(exc: BaseException) -> str:
    return str(_safe_error_message(exc) or "")


def _workflow_error_diff(exc: BaseException) -> Optional[List[str]]:
    if isinstance(exc, ScalimWorkflowWriteError):
        return exc.diff
    return None


def _build_workflow_run_error(exc: BaseException, *, run_id: str, demand_path: str) -> WorkflowRunError:
    return WorkflowRunError(
        run_id=str(run_id),
        demand_path=str(demand_path),
        exc_type=safe_error_type(exc),
        message=safe_error_message(exc),
        diff=_workflow_error_diff(exc),
    )


def build_outcome_from_exception(exc: BaseException, *, run_id: str, demand_path: str) -> WorkflowRunOutcome:
    err = _build_workflow_run_error(exc, run_id=str(run_id), demand_path=str(demand_path))
    return WorkflowRunOutcome(run_id=str(run_id), demand_path=str(demand_path), result=None, error=err)


def build_outcome_from_result(result: object, *, run_id: str, demand_path: str) -> WorkflowRunOutcome:
    return WorkflowRunOutcome(
        run_id=str(run_id),
        demand_path=str(demand_path or ""),
        result=result,
        error=None,
    )


__all__ = ()
