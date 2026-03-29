"""`Scalim` 可视化相关的内置观测器预设.

`scalim.ob.presets.viz` 作为稳定入口:

- `VizObserver`/`VizObserverConfig`: `demand` 运行的可视化导出
- `WorkflowVizObserver`: `workflow` 作用域的可视化导出
"""

from .api import (
    VizEventEmitter,
    VizObserver,
    VizObserverConfig,
    WorkflowVizObserver,
    augment_viz_graph_snapshot_for_output_composition,
    build_workflow_viz_graph_snapshot,
)

__all__ = [
    "VizEventEmitter",
    "VizObserver",
    "VizObserverConfig",
    "WorkflowVizObserver",
    "augment_viz_graph_snapshot_for_output_composition",
    "build_workflow_viz_graph_snapshot",
]
