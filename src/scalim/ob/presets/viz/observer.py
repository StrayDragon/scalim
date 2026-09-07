# region imports

from typing import Any

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
    snapshot: dict[str, Any] | None
    run_id: str | None
    _events_emitter: VizEventEmitter | None
    _trace_emitter: VizEventEmitter | None
    _known_node_ids: set[str] | None
    _node_id_cache: dict[str, str] | None
    _snapshot_written: bool
    _run_dir_applied: bool

    def __init__(
        self,
        *,
        config: VizObserverConfig | None = None,
        snapshot: dict[str, Any] | None = None,
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
    def from_plan(cls, plan: ExecutionPlan, config: VizObserverConfig, *, output_composition: Any | None = None) -> "VizObserver":
        snapshot = plan.to_viz_graph_snapshot()
        if output_composition is not None:
            snapshot = augment_viz_graph_snapshot_for_output_composition(snapshot, output_composition=output_composition)
        return cls(config=config, snapshot=snapshot)


__all__ = ("VizObserver",)
