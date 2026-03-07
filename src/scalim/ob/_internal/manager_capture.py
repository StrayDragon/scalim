# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
from typing import Any, List

from ...events.event import Event
from .common import ObserverCaptureOverflowError


class ObserverManagerCaptureMixin:
    def _record_event(self, event: Event) -> None:
        with self._lock:
            max_recorded_events = self.max_recorded_events
            if max_recorded_events is None:
                self._recorded_events.append(event)
                return

            limit = int(max_recorded_events)
            if limit <= 0:
                if self.capture_overflow_policy == "raise":
                    msg = (
                        "ObserverManager capture recorded events overflow (limit=0). "
                        "Set max_recorded_events to a positive value, or set capture_overflow_policy to 'drop-oldest'/'drop-newest'."
                    )
                    raise ObserverCaptureOverflowError(msg)
                return

            if len(self._recorded_events) < limit:
                self._recorded_events.append(event)
                return

            policy = self.capture_overflow_policy
            if policy == "drop-newest":
                return
            if policy == "drop-oldest":
                _ = self._recorded_events.popleft()
                self._recorded_events.append(event)
                return

            msg = (
                "ObserverManager capture recorded events overflow (size={}, limit={}, policy={}). "
                "Increase max_recorded_events, or set capture_overflow_policy to 'drop-oldest'/'drop-newest'."
            ).format(len(self._recorded_events), limit, policy)
            raise ObserverCaptureOverflowError(msg)

    def drain_events(self) -> List[Event]:
        with self._lock:
            if not self._recorded_events:
                return []
            events = list(self._recorded_events)
            self._recorded_events.clear()
            return events

    def create_capture_manager(self) -> Any:
        manager_cls = type(self)
        capture = manager_cls(
            observers=None,
            enable_debugging=self.debug_mode,
            fallback_logger_enabled=self.fallback_logger_enabled,
            loader_result_policy=self.loader_result_policy,
            loader_result_sample_size=self.loader_result_sample_size,
            run_id=self.run_id,
            mode="capture",
            max_recorded_events=self.max_recorded_events,
            capture_overflow_policy=self.capture_overflow_policy,
        )
        capture._capture_event_types = set(self._supported_event_types)  # noqa: SLF001
        capture._capture_unknown_event_types = bool(self._observers_for_unknown_event_type)  # noqa: SLF001
        return capture
