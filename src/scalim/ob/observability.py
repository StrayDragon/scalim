# region imports

from typing import Any, Dict, List, Optional

from .._internal.utils.loader_result import LoaderResultPolicyLike, normalize_loader_result_policy
from ..vendor.dataclassesx import dataclass
from ._internal.common import ObserverManagerModeLike
from .manager import ObserverManager
from .observer import Observer

# endregion


@dataclass(frozen=True)
class ObservabilityOptions:
    """`Observability` 构造选项(集中校验 + `fail-fast`)."""

    enable_debugging: bool = False
    fallback_logger_enabled: bool = False
    loader_result_policy: LoaderResultPolicyLike = "full"
    loader_result_sample_size: int = 5

    def __post_init__(self) -> None:
        try:
            policy = normalize_loader_result_policy(self.loader_result_policy)
        except (TypeError, ValueError) as exc:
            msg = "ObservabilityOptions.loader_result_policy: {}".format(str(exc))
            raise ValueError(msg) from exc
        object.__setattr__(self, "loader_result_policy", policy)

        sample_size = int(self.loader_result_sample_size)
        if sample_size < 1:
            msg = "ObservabilityOptions.loader_result_sample_size: must be >= 1, got: {!r}".format(self.loader_result_sample_size)
            raise ValueError(msg)
        object.__setattr__(self, "loader_result_sample_size", sample_size)


class Observability:
    """可观测性门面:注册观察者并构建 `ObserverManager`."""

    observers: List[Observer]
    options: ObservabilityOptions

    def __init__(
        self,
        observers: Optional[List[Observer]] = None,
        *,
        options: Optional[ObservabilityOptions] = None,
    ) -> None:
        self.observers = list(observers or [])
        self.options = options or ObservabilityOptions()

    def register(self, observer: Observer) -> None:
        self.observers.append(observer)

    def build_manager(
        self,
        *,
        run_id: Optional[str] = None,
        event_meta_defaults: Optional[Dict[str, Any]] = None,
        mode: ObserverManagerModeLike = "process",
    ) -> ObserverManager:
        return ObserverManager(
            observers=list(self.observers),
            enable_debugging=self.options.enable_debugging,
            fallback_logger_enabled=self.options.fallback_logger_enabled,
            loader_result_policy=self.options.loader_result_policy,
            loader_result_sample_size=self.options.loader_result_sample_size,
            run_id=run_id,
            event_meta_defaults=event_meta_defaults,
            mode=mode,
        )


__all__ = ("Observability", "ObservabilityOptions")
