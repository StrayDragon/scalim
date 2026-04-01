# region imports

from typing import Any, Dict, Optional, Set

from ....planning.plan import ExecutionPlan
from ...observer import EventDispatchObserver
from .._internal.viz_config import VizObserverConfig
from .._internal.viz_handlers import VizObserverHandlerMixin
from .._internal.viz_nodes import VizObserverNodeMixin
from .._internal.viz_output import VizEventEmitter, VizObserverOutputMixin
from .output_composition import augment_viz_graph_snapshot_for_output_composition

# endregion


class VizObserver(VizObserverNodeMixin, VizObserverOutputMixin, VizObserverHandlerMixin, EventDispatchObserver):
    """可视化事件观察者."""

    config: VizObserverConfig
    snapshot: Optional[Dict[str, Any]]
    run_id: Optional[str]
    _events_emitter: Optional[VizEventEmitter]
    _trace_emitter: Optional[VizEventEmitter]
    _known_node_ids: Optional[Set[str]]
    _node_id_cache: Optional[Dict[str, str]]
    _snapshot_written: bool
    _run_dir_applied: bool

    def __init__(
        self,
        *,
        config: Optional[VizObserverConfig] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config = config or VizObserverConfig()
        self.snapshot = snapshot
        self.run_id = None
        self._events_emitter = None
        self._trace_emitter = None
        self._known_node_ids = None
        self._node_id_cache = {}
        self._snapshot_written = False
        self._run_dir_applied = False
        self._attach_viz_metadata()

    @classmethod
    def from_plan(cls, plan: ExecutionPlan, config: VizObserverConfig, *, output_composition: Optional[Any] = None) -> "VizObserver":
        snapshot = plan.to_viz_graph_snapshot()
        if output_composition is not None:
            snapshot = augment_viz_graph_snapshot_for_output_composition(snapshot, output_composition=output_composition)
        return cls(config=config, snapshot=snapshot)


__all__ = ("VizObserver",)
