"""`scalim.ob.presets.viz` 稳定导出面.

说明:
- 对外稳定导入路径仍为 `scalim.ob.presets.viz`
- `_internal` 子包属于实现细节(非公共契约)
"""

from .._internal.viz_config import VizObserverConfig
from .._internal.viz_output import VizEventEmitter
from .observer import VizObserver
from .output_composition import augment_viz_graph_snapshot_for_output_composition
from .workflow import WorkflowVizObserver, build_workflow_viz_graph_snapshot

__all__ = [
    "VizEventEmitter",
    "VizObserver",
    "VizObserverConfig",
    "WorkflowVizObserver",
    "augment_viz_graph_snapshot_for_output_composition",
    "build_workflow_viz_graph_snapshot",
]
