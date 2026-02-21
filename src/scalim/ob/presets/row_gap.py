# region imports

import logging
from collections.abc import Hashable, Iterable, Sized
from typing import Any, cast

from ...events.events import LoaderCallEvent, PipelineEndEvent
from ..observer import EventDispatchObserver

# endregion

_LOGGER = logging.getLogger(__name__)


class RowGapObserver(EventDispatchObserver):
    """记录主数据源行数与批次加载的行缺口统计."""

    primary_loader_name: str
    data_loader_names: set[str]
    sample_limit: int
    logger: logging.Logger

    _primary_count: int | None
    _total_expected: int
    _total_actual: int
    _total_missing: int

    def __init__(
        self,
        primary_loader_name: str = "primary_keys",
        data_loader_names: Iterable[str] | None = None,
        sample_limit: int = 5,
        logger: logging.Logger | None = None,
    ) -> None:
        self.primary_loader_name = primary_loader_name
        self.data_loader_names = set(data_loader_names or ["base_info"])
        self.sample_limit = max(sample_limit, 0)
        self.logger = logger or _LOGGER

        self._primary_count = None
        self._total_expected = 0
        self._total_actual = 0
        self._total_missing = 0

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        if event.loader_name == self.primary_loader_name:
            result_size = self._result_size(event.result)
            self._primary_count = result_size
            self.logger.info(
                "[RowGap] main_rows=%s loader=%s",
                result_size,
                event.loader_name,
            )
            return

        if event.loader_name not in self.data_loader_names:
            return

        expected_keys = self._extract_expected_keys(event.params)
        expected_len = len(expected_keys) if expected_keys is not None else None
        actual_len = self._result_size(event.result)
        missing = None

        if expected_len is not None:
            missing = max(expected_len - actual_len, 0)
            self._total_expected += expected_len
            self._total_actual += actual_len
            self._total_missing += missing

        sample_missing: list[Hashable] = []
        if expected_keys is not None and isinstance(event.result, dict) and self.sample_limit > 0:
            result_dict = cast("dict[Hashable, Any]", event.result)
            for key in expected_keys:
                try:
                    if key not in result_dict:
                        sample_missing.append(key)
                        if len(sample_missing) >= self.sample_limit:
                            break
                except TypeError:
                    continue

        self.logger.info(
            "[RowGap] loader=%s expected=%s actual=%s missing=%s sample_missing=%s",
            event.loader_name,
            expected_len,
            actual_len,
            missing,
            sample_missing or None,
        )

    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        _ = event
        if self._total_expected:
            self.logger.info(
                "[RowGap] total expected=%s actual=%s missing=%s main_rows=%s",
                self._total_expected,
                self._total_actual,
                self._total_missing,
                self._primary_count,
            )

    @staticmethod
    def _result_size(result: Any) -> int:
        if isinstance(result, Sized):
            return len(result)
        return 0

    @staticmethod
    def _extract_expected_keys(params: dict[str, Any]) -> list[Hashable] | None:
        if not params:
            return None
        for key in ("user_ids", "batch_row_nth", "batch_keys", "user_id_list", "keys", "ids"):
            if key in params:
                value = params.get(key)
                if value is None:
                    return None
                if isinstance(value, dict):
                    value_dict = cast("dict[Hashable, Any]", value)
                    return list(value_dict.keys())
                if isinstance(value, (list, tuple, set)):
                    value_iter = cast("Iterable[Hashable]", value)
                    return list(value_iter)
                return None
        return None


__all__ = [
    "RowGapObserver",
]
