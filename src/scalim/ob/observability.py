# region imports


from .manager import ObserverManager
from .observer import Observer

# endregion


class Observability:
    """Observability facade: registers observers and builds ObserverManager."""

    observers: list[Observer]
    enable_debugging: bool
    fallback_logger_enabled: bool
    loader_result_policy: str
    loader_result_sample_size: int

    def __init__(
        self,
        observers: list[Observer] | None = None,
        *,
        enable_debugging: bool = False,
        fallback_logger_enabled: bool = False,
        loader_result_policy: str = "full",
        loader_result_sample_size: int = 5,
    ) -> None:
        self.observers = list(observers or [])
        self.enable_debugging = enable_debugging
        self.fallback_logger_enabled = fallback_logger_enabled
        self.loader_result_policy = loader_result_policy
        self.loader_result_sample_size = loader_result_sample_size

    def register(self, observer: Observer) -> None:
        self.observers.append(observer)

    def build_manager(self, *, run_id: str | None = None, mode: str = "process") -> ObserverManager:
        return ObserverManager(
            observers=list(self.observers),
            enable_debugging=self.enable_debugging,
            fallback_logger_enabled=self.fallback_logger_enabled,
            loader_result_policy=self.loader_result_policy,
            loader_result_sample_size=self.loader_result_sample_size,
            run_id=run_id,
            mode=mode,
        )


__all__ = [
    "Observability",
]
