import contextlib
import threading
from typing import Any, FrozenSet, Iterator, Mapping

from ..vendor.compact.typing_extensionsx import TypeGuard
from ..vendor.dataclassesx import dataclass
from .resources import WorkflowResourceManager


@dataclass(frozen=True)
class _WorkflowLoaderContext:
    workflow_exec_id: str
    workflow_node_id: str
    visible_producer_node_ids: FrozenSet[str]
    resource_manager: WorkflowResourceManager


_TLS = threading.local()


def _is_mapping(value: object) -> TypeGuard[Mapping[str, Any]]:
    return isinstance(value, dict)


@contextlib.contextmanager
def workflow_loader_context(
    *,
    workflow_exec_id: str,
    workflow_node_id: str,
    visible_producer_node_ids: FrozenSet[str],
    resource_manager: WorkflowResourceManager,
) -> Iterator[None]:
    """在执行一个 `workflow` 的 `demand` 节点时,注入内置 `workflow loader` 所需上下文(`thread-local`)."""
    try:
        prev = _TLS.ctx
    except AttributeError:
        prev = None
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
                del _TLS.ctx
            except AttributeError:
                return
        else:
            _TLS.ctx = prev


def _require_context() -> _WorkflowLoaderContext:
    try:
        ctx = _TLS.ctx
    except AttributeError:
        ctx = None
    if ctx is None:
        msg = "workflow loader requires workflow context (only valid inside run_workflow execution)"
        raise ValueError(msg)
    if not isinstance(ctx, _WorkflowLoaderContext):
        msg = "workflow loader context is corrupted (expected _WorkflowLoaderContext, got {})".format(type(ctx).__name__)
        raise TypeError(msg)
    return ctx


def book_sheet_rows(*, ref: object) -> Iterator[Mapping[str, object]]:
    """内置 `loader`: 读取 `workflow` `books.kind=xlsx_memory` 的某个 `sheet` 行数据(`rows`).

    参数:
    - `ref`: 映射对象,必填键: `node`/`book`/`sheet`
    """
    ctx = _require_context()

    if not _is_mapping(ref):
        msg = "book_sheet_rows requires params.ref as a mapping"
        raise TypeError(msg)
    ref_dict = ref

    producer_node_id = str(ref_dict.get("node", "") or "").strip()
    book_id = str(ref_dict.get("book", "") or "").strip()
    sheet_name = str(ref_dict.get("sheet", "") or "").strip()

    if not producer_node_id:
        msg = "book_sheet_rows ref.node must be a non-empty string"
        raise ValueError(msg)
    if not book_id:
        msg = "book_sheet_rows ref.book must be a non-empty string"
        raise ValueError(msg)
    if not sheet_name:
        msg = "book_sheet_rows ref.sheet must be a non-empty string"
        raise ValueError(msg)

    consumer_node_id = str(ctx.workflow_node_id)
    visible = ctx.visible_producer_node_ids
    if producer_node_id != consumer_node_id and producer_node_id not in visible:
        msg = "Book ref node {!r} is not visible to node {!r} (declare depends_on)".format(producer_node_id, consumer_node_id)
        raise ValueError(msg)

    return ctx.resource_manager.iter_book_sheet_rows(
        consumer_node_id=consumer_node_id,
        visible_producer_node_ids=visible,
        producer_node_id=producer_node_id,
        book_id=book_id,
        sheet=sheet_name,
    )


__all__ = [
    "book_sheet_rows",
    "workflow_loader_context",
]
