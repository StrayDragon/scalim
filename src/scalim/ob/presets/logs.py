# region imports

import logging
import sys
from typing import Any, Dict, Optional

from ..._internal.loggingx import format_kv, get_logger, prefix
from ...events import Event
from .._internal.console_report import build_line, format_seconds
from ..observer import EventDispatchObserver
from ..structured_logging import emit_structured, is_jsonl_logging_installed

# endregion

_LOGGER = get_logger("pipeline")
_PRETTY_LOGGER = get_logger("pretty")
_PRETTY_STDOUT_HANDLER_NAME = "scalim.pretty.stdout"

LOGGING_OBSERVER_LOADER_SLIM_LOG = prefix("pipeline") + "加载器瘦身"
LOGGING_OBSERVER_COLUMN_WRITE_LOG = prefix("pipeline") + "写入列"


class _PrettyStdoutHandlerSlot:
    handler: Optional[logging.Handler]
    owned: bool

    def __init__(self) -> None:
        self.handler = None
        self.owned = False


_pretty_stdout_handler_slot = _PrettyStdoutHandlerSlot()


class LoggingObserver(EventDispatchObserver):
    """日志观察者:将执行进度写入日志系统"""

    logger: logging.Logger

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        if logger is None:
            logger = _LOGGER
        self.logger = logger

    def on_pipeline_start(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.INFO,
                kind="pipeline.start",
                message="pipeline_start",
                fields={
                    "target_fields": len(payload.targets),
                    "batch_size": payload.batch_size,
                },
            )
            return
        batch_size_text = "all" if payload.batch_size is None else str(payload.batch_size)
        kv = format_kv(target_fields=len(payload.targets), batch_size=batch_size_text)
        self.logger.info("%s管道启动 %s", prefix("pipeline"), kv)

    def on_pipeline_end(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.INFO,
                kind="pipeline.end",
                message="pipeline_end",
                fields={
                    "batches": int(payload.total_batches),
                    "total_duration_s": float(payload.total_duration),
                },
            )
            return
        kv = format_kv(batches=payload.total_batches, total_duration_s="{:.2f}".format(float(payload.total_duration)))
        self.logger.info("%s管道完成 %s", prefix("pipeline"), kv)

    def on_batch_start(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.INFO,
                kind="pipeline.batch_start",
                message="batch_start",
                fields={
                    "batch_num": int(payload.batch_num),
                    "row_count": len(payload.row_ids),
                },
            )
            return
        kv = format_kv(batch_num=payload.batch_num, row_count=len(payload.row_ids))
        self.logger.info("%s批次开始 %s", prefix("pipeline"), kv)

    def on_batch_end(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.INFO,
                kind="pipeline.batch_end",
                message="batch_end",
                fields={
                    "batch_num": int(payload.batch_num),
                    "duration_s": float(payload.duration),
                },
            )
            return
        kv = format_kv(batch_num=payload.batch_num, duration_s="{:.2f}".format(float(payload.duration)))
        self.logger.info("%s批次完成 %s", prefix("pipeline"), kv)

    def on_loader_call(self, event: Event) -> None:
        payload = event.payload
        loader_result: Any = payload.result
        try:
            result_size = len(loader_result)
        except (TypeError, AttributeError):
            result_size = 0
        cache_status = None
        cache_fields = None
        if payload.cache_status:
            if payload.field_keys:
                cache_fields = ",".join(payload.field_keys)
            cache_status = str(payload.cache_status)
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.INFO,
                kind="pipeline.loader_call",
                message="loader_call",
                fields={
                    "loader_name": str(payload.loader_name),
                    "result_count": int(result_size),
                    "duration_s": float(payload.duration),
                    "cache_status": cache_status,
                    "cache_fields": cache_fields,
                },
            )
            return
        kv = format_kv(
            loader_name=payload.loader_name,
            result_count=int(result_size),
            duration_s="{:.2f}".format(float(payload.duration)),
            cache_status=cache_status,
            cache_fields=cache_fields,
        )
        self.logger.info("%s加载 %s", prefix("pipeline"), kv)

    def on_field_compute(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.DEBUG,
                kind="pipeline.field_compute",
                message="field_compute",
                fields={
                    "field_key": str(payload.field_key),
                    "row_id": payload.row_id,
                    "result": payload.result,
                },
            )
            return
        kv = format_kv(field_key=payload.field_key, row_id=payload.row_id, result=payload.result)
        self.logger.debug("%s计算 %s", prefix("pipeline"), kv)

    def on_error(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.ERROR,
                kind="pipeline.error",
                message="error",
                fields={
                    "error_type": str(payload.error_type),
                    "error_message": str(payload.error_message),
                },
            )
            return
        self.logger.error("%s错误[%s]: %s", prefix("pipeline"), str(payload.error_type), str(payload.error_message))
        if payload.context:
            for key, ctx_value in payload.context.items():
                self.logger.error("%s  %s: %s", prefix("pipeline"), key, ctx_value)

    def on_diagnostic_warning(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.WARNING,
                kind="pipeline.diagnostic_warning",
                message="diagnostic_warning",
                fields={
                    "warning_message": str(payload.message),
                    "source_id": str(payload.source_id),
                    "field_id": str(payload.field_id),
                    "row_id": payload.row_id,
                    "lookup_key": payload.lookup_key,
                },
            )
            return
        kv = format_kv(
            message=payload.message,
            source_id=payload.source_id,
            field_id=payload.field_id,
            row_id=payload.row_id,
            lookup_key=payload.lookup_key,
        )
        self.logger.warning("%s诊断警告 %s", prefix("pipeline"), kv)

    def on_field_slim(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.DEBUG,
                kind="pipeline.field_slim",
                message="field_slim",
                fields={
                    "field_key": str(payload.field_key),
                    "reason": str(payload.reason),
                },
            )
            return
        kv = format_kv(field_key=payload.field_key, reason=payload.reason)
        self.logger.debug("%s字段瘦身 %s", prefix("pipeline"), kv)

    def on_row_write(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.DEBUG,
                kind="pipeline.row_write",
                message="row_write",
                fields={
                    "row_id": payload.row_id,
                    "field_count": int(payload.field_count),
                },
            )
            return
        kv = format_kv(row_id=payload.row_id, field_count=payload.field_count)
        self.logger.debug("%s写入行 %s", prefix("pipeline"), kv)

    def on_row_release(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.DEBUG,
                kind="pipeline.row_release",
                message="row_release",
                fields={
                    "row_id": payload.row_id,
                    "released_count": len(payload.released_fields),
                    "retained_count": len(payload.retained_fields),
                },
            )
            return
        kv = format_kv(
            row_id=payload.row_id,
            released_count=len(payload.released_fields),
            retained_count=len(payload.retained_fields),
        )
        self.logger.debug("%s释放行 %s", prefix("pipeline"), kv)

    def on_loader_slim(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.DEBUG,
                kind="pipeline.loader_slim",
                message="loader_slim",
                fields={
                    "loader_name": str(payload.loader_name),
                    "original_keys": int(payload.original_keys),
                    "extracted_fields": list(payload.extracted_fields) if payload.extracted_fields else None,
                },
            )
            return
        kv = format_kv(loader_name=payload.loader_name, original_keys=payload.original_keys)
        self.logger.debug("%s加载器瘦身 %s", prefix("pipeline"), kv)

    def on_column_write(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                self.logger,
                level=logging.DEBUG,
                kind="pipeline.column_write",
                message="column_write",
                fields={
                    "field_key": str(payload.field_key),
                    "row_count": int(payload.row_count),
                },
            )
            return
        kv = format_kv(field_key=payload.field_key, row_count=payload.row_count)
        self.logger.debug("%s写入列 %s", prefix("pipeline"), kv)


class PrettyLoggingObserver(EventDispatchObserver):
    _loader_stats: Dict[str, Dict[str, Any]]
    _total_rows: int

    def __init__(self) -> None:
        self._ensure_pretty_logger_ready()
        self._loader_stats = {}
        self._total_rows = 0

    @staticmethod
    def _ensure_pretty_logger_ready() -> None:
        """确保 `pretty` 输出写入当前 `sys.stdout`.

        说明:
        - `pytest capsys` 会在每个测试用例中替换 `sys.stdout` 对象;若复用旧的 `StreamHandler.stream`,
          会导致输出无法被当前用例捕获.
        - 若用户已自行向 `scalim.pretty` 绑定同名 `handler`,则优先复用该 `handler`,避免覆盖/重复输出.
        """

        if is_jsonl_logging_installed():
            owned_handler = _pretty_stdout_handler_slot.handler if _pretty_stdout_handler_slot.owned else None
            if owned_handler is not None and owned_handler in _PRETTY_LOGGER.handlers:
                _PRETTY_LOGGER.removeHandler(owned_handler)
            _pretty_stdout_handler_slot.handler = None
            _pretty_stdout_handler_slot.owned = False
            _PRETTY_LOGGER.setLevel(logging.INFO)
            _PRETTY_LOGGER.propagate = True
            return

        fmt = logging.Formatter("%(message)s")

        owned_handler = _pretty_stdout_handler_slot.handler if _pretty_stdout_handler_slot.owned else None

        user_named_handler: Optional[logging.Handler] = None
        for handler in _PRETTY_LOGGER.handlers:
            if handler.name != _PRETTY_STDOUT_HANDLER_NAME:
                continue
            if owned_handler is not None and handler is owned_handler:
                continue
            user_named_handler = handler
            break

        if user_named_handler is not None:
            if owned_handler is not None and owned_handler in _PRETTY_LOGGER.handlers:
                _PRETTY_LOGGER.removeHandler(owned_handler)
            _pretty_stdout_handler_slot.handler = user_named_handler
            _pretty_stdout_handler_slot.owned = False
        else:
            if owned_handler is not None and owned_handler in _PRETTY_LOGGER.handlers:
                _PRETTY_LOGGER.removeHandler(owned_handler)
            handler = logging.StreamHandler(stream=sys.stdout)
            handler.name = _PRETTY_STDOUT_HANDLER_NAME
            handler.setFormatter(fmt)
            _PRETTY_LOGGER.addHandler(handler)
            _pretty_stdout_handler_slot.handler = handler
            _pretty_stdout_handler_slot.owned = True

        _PRETTY_LOGGER.setLevel(logging.INFO)
        _PRETTY_LOGGER.propagate = False

    def on_pipeline_start(self, event: Event) -> None:
        payload = event.payload
        batch_size_text = "all" if payload.batch_size is None else str(payload.batch_size)
        self._loader_stats = {}
        self._total_rows = 0
        if is_jsonl_logging_installed():
            emit_structured(
                _PRETTY_LOGGER,
                level=logging.INFO,
                kind="pretty.pipeline_start",
                message="pipeline_start",
                fields={
                    "target_fields": len(payload.targets),
                    "batch_size": payload.batch_size,
                },
            )
            return
        _PRETTY_LOGGER.info(
            "%s",
            build_line("pretty", "pipeline_start", target_fields=len(payload.targets), batch_size=str(batch_size_text)),
        )

    def on_pipeline_end(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                _PRETTY_LOGGER,
                level=logging.INFO,
                kind="pretty.pipeline_end",
                message="pipeline_end",
                fields={
                    "batches": int(payload.total_batches),
                    "total_duration_s": float(payload.total_duration),
                    "total_rows": int(self._total_rows),
                },
            )
        else:
            _PRETTY_LOGGER.info(
                "%s",
                build_line(
                    "pretty",
                    "pipeline_end",
                    batches=int(payload.total_batches),
                    total_duration_s=format_seconds(float(payload.total_duration), digits=2),
                    total_rows=int(self._total_rows),
                ),
            )

        if self._loader_stats:
            for name in sorted(self._loader_stats.keys()):
                stats = self._loader_stats[name]
                calls = int(stats.get("calls") or 0)
                total_duration = float(stats.get("total_duration") or 0.0)
                avg_time = (total_duration / calls) if calls else 0.0
                if is_jsonl_logging_installed():
                    emit_structured(
                        _PRETTY_LOGGER,
                        level=logging.INFO,
                        kind="pretty.loader",
                        message="loader",
                        fields={
                            "loader_name": str(name),
                            "calls": int(calls),
                            "records": int(stats.get("records") or 0),
                            "total_duration_s": float(total_duration),
                            "avg_duration_s": float(avg_time),
                            "cache_hit": int(stats.get("cache_hit") or 0) or None,
                            "cache_miss": int(stats.get("cache_miss") or 0) or None,
                        },
                    )
                else:
                    _PRETTY_LOGGER.info(
                        "%s",
                        build_line(
                            "pretty",
                            "loader",
                            loader=str(name),
                            calls=int(calls),
                            records=int(stats.get("records") or 0),
                            total_duration_s=format_seconds(total_duration, digits=3),
                            avg_time_s=format_seconds(avg_time, digits=4),
                            cache_hit=int(stats.get("cache_hit") or 0) or None,
                            cache_miss=int(stats.get("cache_miss") or 0) or None,
                        ),
                    )

    def on_batch_start(self, event: Event) -> None:
        payload = event.payload
        self._total_rows += len(payload.row_ids)

    def on_batch_end(self, event: Event) -> None:
        payload = event.payload
        if is_jsonl_logging_installed():
            emit_structured(
                _PRETTY_LOGGER,
                level=logging.INFO,
                kind="pretty.batch_end",
                message="batch_end",
                fields={
                    "batch_num": int(payload.batch_num),
                    "duration_s": float(payload.duration),
                },
            )
            return
        _PRETTY_LOGGER.info(
            "%s",
            build_line(
                "pretty",
                "batch_end",
                batch_num=int(payload.batch_num),
                duration_s=format_seconds(float(payload.duration), digits=2),
            ),
        )

    def on_loader_call(self, event: Event) -> None:
        payload = event.payload
        result_count = 0
        try:
            result_count = len(payload.result)  # type: ignore[arg-type]
        except TypeError:
            result_count = 0
        name = str(payload.loader_name or "")
        if not name:
            name = "<unknown>"

        entry = self._loader_stats.get(name)
        if entry is None:
            entry = {"calls": 0, "records": 0, "total_duration": 0.0, "cache_hit": 0, "cache_miss": 0}
            self._loader_stats[name] = entry

        entry["calls"] = int(entry.get("calls") or 0) + 1
        entry["records"] = int(entry.get("records") or 0) + int(result_count)
        entry["total_duration"] = float(entry.get("total_duration") or 0.0) + float(payload.duration)
        if payload.cache_status == "hit":
            entry["cache_hit"] = int(entry.get("cache_hit") or 0) + 1
        elif payload.cache_status == "miss":
            entry["cache_miss"] = int(entry.get("cache_miss") or 0) + 1


__all__ = (
    "LoggingObserver",
    "PrettyLoggingObserver",
)
