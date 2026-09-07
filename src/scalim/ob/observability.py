# region imports

from dataclasses import dataclass
from typing import Any

from .._internal.utils.loader_result import LoaderResultPolicy
from .._internal.utils.policy import ensure_policy_enum
from ._internal.common import ObserverManagerMode
from .manager import ObserverManager
from .observer import Observer

# endregion


@dataclass(frozen=True)
class ObservabilityOptions:
    """`Observability` 构造选项(集中校验 + `fail-fast`)."""

    enable_debugging: bool = False
    fallback_logger_enabled: bool = False
    loader_result_policy: LoaderResultPolicy = LoaderResultPolicy.FULL
    loader_result_sample_size: int = 5

    def __post_init__(self) -> None:
        try:
            policy = ensure_policy_enum(LoaderResultPolicy, self.loader_result_policy, label="ObservabilityOptions.loader_result_policy")
        except TypeError as exc:
            msg = f"ObservabilityOptions.loader_result_policy: {exc!s}"
            raise TypeError(msg) from exc
        object.__setattr__(self, "loader_result_policy", policy)

        sample_size = int(self.loader_result_sample_size)
        if sample_size < 1:
            msg = f"ObservabilityOptions.loader_result_sample_size: must be >= 1, got: {self.loader_result_sample_size!r}"
            raise ValueError(msg)
        object.__setattr__(self, "loader_result_sample_size", sample_size)


class Observability:
    """可观测性门面:注册观察者并构建 `ObserverManager`."""

    observers: list[Observer]
    options: ObservabilityOptions

    def __init__(
        self,
        observers: list[Observer] | None = None,
        *,
        options: ObservabilityOptions | None = None,
    ) -> None:
        self.observers = list(observers or [])
        self.options = options or ObservabilityOptions()

    def register(self, observer: Observer) -> None:
        self.observers.append(observer)

    def build_manager(
        self,
        *,
        run_id: str | None = None,
        event_meta_defaults: dict[str, Any] | None = None,
        mode: ObserverManagerMode = ObserverManagerMode.PROCESS,
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
