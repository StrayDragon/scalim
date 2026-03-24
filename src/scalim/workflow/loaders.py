import contextlib
import threading
from dataclasses import dataclass
from typing import Any, FrozenSet, Iterator, Mapping, cast

from .resources import WorkflowResourceManager


@dataclass(frozen=True)
class _WorkflowLoaderContext:
    workflow_exec_id: str
    workflow_node_id: str
    visible_producer_node_ids: FrozenSet[str]
    resource_manager: WorkflowResourceManager


_TLS = threading.local()


@contextlib.contextmanager
def workflow_loader_context(
    *,
    workflow_exec_id: str,
    workflow_node_id: str,
    visible_producer_node_ids: FrozenSet[str],
    resource_manager: WorkflowResourceManager,
) -> Iterator[None]:
    """在执行一个 `workflow` 的 `demand` 节点时,注入内置 `workflow loader` 所需上下文(`thread-local`)."""
    prev = getattr(_TLS, "ctx", None)
    _TLS.ctx = _WorkflowLoaderContext(
        workflow_exec_id=str(workflow_exec_id),
        workflow_node_id=str(workflow_node_id),
        visible_producer_node_ids=frozenset(str(x) for x in visible_producer_node_ids),
        resource_manager=resource_manager,
    )
    try:
        yield
    finally:
        if prev is None:
            try:
                delattr(_TLS, "ctx")
            except AttributeError:
                return
        else:
            _TLS.ctx = prev


def _require_context() -> _WorkflowLoaderContext:
    ctx = getattr(_TLS, "ctx", None)
    if ctx is None:
        msg = "workflow loader requires workflow context (only valid inside run_workflow execution)"
        raise ValueError(msg)
    return cast("_WorkflowLoaderContext", ctx)


def sheetbook_sheet_rows(*, ref: object) -> Iterator[Mapping[str, object]]:
    """内置 `loader`: 读取 `workflow` `sheetbook` 的 `sheet` 行数据(`rows`).

    参数:
    - `ref`: 映射对象,必填键: `node`/`sheetbook`/`sheet`
    """
    ctx = _require_context()

    if not isinstance(ref, dict):
        msg = "sheetbook_sheet_rows requires params.ref as a mapping"
        raise TypeError(msg)
    ref_dict = cast("Mapping[str, Any]", ref)

    producer_node_id = str(ref_dict.get("node", "") or "").strip()
    sheetbook_id = str(ref_dict.get("sheetbook", "") or "").strip()
    sheet_name = str(ref_dict.get("sheet", "") or "").strip()

    if not producer_node_id:
        msg = "sheetbook_sheet_rows ref.node must be a non-empty string"
        raise ValueError(msg)
    if not sheetbook_id:
        msg = "sheetbook_sheet_rows ref.sheetbook must be a non-empty string"
        raise ValueError(msg)
    if not sheet_name:
        msg = "sheetbook_sheet_rows ref.sheet must be a non-empty string"
        raise ValueError(msg)

    consumer_node_id = str(ctx.workflow_node_id)
    visible = ctx.visible_producer_node_ids
    if producer_node_id != consumer_node_id and producer_node_id not in visible:
        msg = "Sheetbook ref node {!r} is not visible to node {!r} (declare depends_on)".format(producer_node_id, consumer_node_id)
        raise ValueError(msg)

    return ctx.resource_manager.iter_sheetbook_sheet_rows(
        consumer_node_id=consumer_node_id,
        visible_producer_node_ids=visible,
        producer_node_id=producer_node_id,
        sheetbook_id=sheetbook_id,
        sheet=sheet_name,
    )


__all__ = [
    "sheetbook_sheet_rows",
    "workflow_loader_context",
]
