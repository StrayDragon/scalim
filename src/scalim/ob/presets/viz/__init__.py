"""`Scalim` 可视化相关的内置观测器预设.

`scalim.ob.presets.viz` 作为稳定入口:

- `VizObserver`/`VizObserverConfig`: `demand` 运行的可视化导出
- `WorkflowVizObserver`: `workflow` 作用域的可视化导出
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
