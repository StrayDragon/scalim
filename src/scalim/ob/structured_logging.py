"""`scalim.*` 的 `JSONL` 结构化日志(运行时, `Python 3.6` 兼容).

设计目标(运行时):
- 仅依赖标准库(无第三方依赖).
- 未显式启用时不干预 `root logger`.
- 启用后: 所有 `scalim.*` 日志器统一输出为 `JSONL`(每条日志一行 `JSON object`).
- 支持基于 `thread-local` 的归因上下文注入(`run`/`workflow`/`demand`).
- 支持 `compact`/`verbose` 两种 `key profile`, 并由 `key registry` 作为 `SSOT`(全称 + 唯一缩写)治理.
"""

import json
import logging
import os
import sys
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Mapping, Optional, Set, Tuple, cast

from ..typedefs import RuntimeValue
from ..vendor.compact.typing_extensionsx import Literal, override

StructuredLogProfile = Literal["compact", "verbose"]

ENV_SCALIM_LOG_FORMAT = "SCALIM_LOG_FORMAT"
ENV_SCALIM_LOG_PROFILE = "SCALIM_LOG_PROFILE"
ENV_SCALIM_LOG_STREAM = "SCALIM_LOG_STREAM"

_SCALIM_ROOT_LOGGER_NAME = "scalim"
_JSONL_HANDLER_NAME = "scalim.jsonl"


def _normalize_bool_env(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text in ("1", "true", "yes", "on")


def _normalize_profile(value: str) -> StructuredLogProfile:
    text = str(value or "").strip().lower()
    if text == "verbose":
        return "verbose"
    return "compact"


def _normalize_stream_name(value: str) -> str:
    text = str(value or "").strip().lower()
    if text == "stdout":
        return "stdout"
    return "stderr"


def _as_json_dict(value: RuntimeValue) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        items = cast("Mapping[object, Any]", value).items()  # pragma: allow-cast narrowing
        return {str(k): v for k, v in items}
    return None


def _format_exception(exc_info: Any) -> Optional[Dict[str, Any]]:
    if not exc_info or exc_info is True:
        return None

    exc_type: Any = None
    exc: Any = None
    if isinstance(exc_info, BaseException):
        exc = exc_info
        exc_type = type(exc_info)
    elif isinstance(exc_info, tuple):
        try:
            exc_type, exc, _tb = cast("Tuple[Any, Any, Any]", exc_info)  # pragma: allow-cast narrowing
        except ValueError:
            return None

    if exc_type is None and exc is None:
        return None

    exc_type_name = exc_type.__name__ if isinstance(exc_type, type) else None
    try:
        exc_message = str(exc) if exc is not None else None
    except (TypeError, ValueError):  # 防御性兜底
        exc_message = "<unprintable>"
    return {
        "error_type": exc_type_name,
        "error_message": exc_message,
    }


# region key registry

# `SSOT`: 全称键 -> 唯一缩写键(在所有已注册键中全局唯一).
_FULL_TO_ABBR: Dict[str, str] = {
    # 基础字段
    "timestamp": "ts",
    "level": "lvl",
    "logger": "lg",
    "message": "msg",
    # 结构化分区
    "kind": "k",
    "context": "ctx",
    "fields": "f",
    "error": "err",
    # 上下文键(可 `join` 的归因字段)
    "run_id": "rid",
    "workflow_exec_id": "wfx",
    "workflow_node_id": "wni",
    "workflow_node_decl_order": "wnd",
    "demand": "dem",
    "demand_path": "dmp",
    # 通用/`pipeline` 字段
    "target_fields": "tfs",
    "batch_size": "bsz",
    "batches": "bch",
    "batch_num": "bn",
    "row_count": "rc",
    "duration_s": "dur",
    "total_duration_s": "tds",
    "loader_name": "ldr",
    "result_count": "cnt",
    "cache_status": "cst",
    "cache_fields": "cfd",
    "field_key": "fk",
    "row_id": "row",
    "field_count": "fc",
    "released_count": "rel",
    "retained_count": "ret",
    "reason": "rsn",
    "source_id": "sid",
    "field_id": "fid",
    "lookup_key": "lk",
    "warning_message": "wmsg",
    "original_keys": "ok",
    "extracted_fields": "efs",
    "error_type": "ety",
    "error_message": "em",
    "avg_duration_s": "avd",
    "cache_hit": "ch",
    "cache_miss": "cm",
    "memory_mb": "mmb",
    "cpu_percent": "cpu",
    # `relations` 字段
    "fk_raw": "fkr",
    "fk_type": "fkt",
    "expected_type": "ext",
    "target_source": "tsr",
    "total_lookups": "tl",
    "hit_count": "hc",
    "miss_count": "mc",
    "null_key_count": "nkc",
    "type_mismatch_count": "tmc",
    "hit_rate": "hr",
    "showing": "shw",
    # `performance` 字段
    "total_rows": "rows",
    "throughput_rows_s": "rps",
    "batch_count": "bc",
    "avg_batch_duration_s": "abd",
    "peak_memory_mb": "pmm",
    "memory_increase_mb": "mim",
    "stage": "stg",
    "percent": "pct",
    "stream_s": "stm",
    "source_lookup_s": "slk",
    "compute_s": "cmp",
    "write_s": "wrt",
    "untracked_overhead_s": "ohs",
    "total_s": "tot",
    "exec_calls": "exc",
    "calls": "cal",
    "records": "rec",
    "cache_hit_rate": "chr",
    "min_s": "mins",
    "max_s": "maxs",
    "p50_s": "p50",
    "p90_s": "p90",
    "stddev_s": "std",
    "field": "fld",
    "hint": "hnt",
    "severity": "sev",
}


def _assert_unique_abbreviations(full_to_abbr: Mapping[str, str]) -> None:
    dup_abbr: List[str] = []
    seen: Set[str] = set()
    for abbr in full_to_abbr.values():
        if abbr in seen:
            dup_abbr.append(str(abbr))
        else:
            seen.add(str(abbr))
    if dup_abbr:
        message = "Duplicate structured-log abbreviations detected: {}".format(sorted(set(dup_abbr)))
        raise RuntimeError(message)


_assert_unique_abbreviations(_FULL_TO_ABBR)

_ABBR_TO_FULL: Dict[str, str] = {abbr: full for full, abbr in _FULL_TO_ABBR.items()}


def full_to_abbr_key(full_key: str) -> Optional[str]:
    return _FULL_TO_ABBR.get(str(full_key))


def abbr_to_full_key(abbr_key: str) -> Optional[str]:
    return _ABBR_TO_FULL.get(str(abbr_key))


def normalize_keys_to_full(obj: Any) -> Any:
    """递归地把已知缩写键映射为全称键(尽力而为)."""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for key, value in cast("Mapping[object, Any]", obj).items():  # pragma: allow-cast narrowing
            full = abbr_to_full_key(str(key)) or str(key)
            out[full] = normalize_keys_to_full(value)
        return out
    if isinstance(obj, list):
        return [normalize_keys_to_full(x) for x in cast("List[Any]", obj)]  # pragma: allow-cast narrowing
    return obj


def apply_profile(obj: Any, profile: StructuredLogProfile) -> Any:
    """递归地把已知全称键映射为缩写键(用于 `compact` 输出档位)."""
    if profile != "compact":
        return obj
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for key, value in cast("Mapping[object, Any]", obj).items():  # pragma: allow-cast narrowing
            key_text = str(key)
            abbr = full_to_abbr_key(key_text) or key_text
            out[abbr] = apply_profile(value, profile)
        return out
    if isinstance(obj, list):
        return [apply_profile(x, profile) for x in cast("List[Any]", obj)]  # pragma: allow-cast narrowing
    return obj


# endregion


# region thread-local context


class _LogContextState:
    __slots__: Tuple[str, ...] = ("stack",)

    def __init__(self) -> None:
        self.stack: List[Dict[str, Any]] = []


_log_context_local = threading.local()


def _state() -> _LogContextState:
    try:
        state = _log_context_local.state
    except AttributeError:
        state = None
    if state is None:
        state = _LogContextState()
        _log_context_local.state = state
    return state


def get_log_context() -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for entry in _state().stack:
        merged.update(entry)
    return merged


@contextmanager
def log_context(**ctx: Any) -> Iterator[None]:
    stack = _state().stack
    stack.append(dict(ctx))
    try:
        yield
    finally:
        if stack:
            _ = stack.pop()


# endregion


class JsonlFormatter(logging.Formatter):
    profile: StructuredLogProfile

    def __init__(self, *, profile: StructuredLogProfile) -> None:
        super().__init__()
        self.profile = profile

    @override
    def format(self, record: logging.LogRecord) -> str:  # 与 `logging.Formatter` 接口对齐
        base: Dict[str, Any] = {
            "timestamp": float(record.created),
            "level": int(record.levelno),
            "logger": str(record.name),
            "message": record.getMessage(),
        }

        kind = record.__dict__.get("scalim_kind")
        if kind:
            base["kind"] = str(kind)

        fields = _as_json_dict(record.__dict__.get("scalim_fields"))
        if fields:
            base["fields"] = fields

        ctx = get_log_context()
        extra_ctx = _as_json_dict(record.__dict__.get("scalim_ctx"))
        if extra_ctx:
            merged = dict(ctx)
            merged.update(extra_ctx)
            ctx = merged
        if ctx:
            base["context"] = ctx

        err = _format_exception(record.exc_info)
        extra_err = _as_json_dict(record.__dict__.get("scalim_error"))
        if extra_err:
            merged_err = dict(err or {})
            merged_err.update(extra_err)
            err = merged_err
        if err:
            base["error"] = err

        profiled = apply_profile(base, self.profile)
        return json.dumps(profiled, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def is_jsonl_logging_installed() -> bool:
    logger = logging.getLogger(_SCALIM_ROOT_LOGGER_NAME)
    return any(h.get_name() == _JSONL_HANDLER_NAME for h in logger.handlers)


def install_jsonl_logging(
    *,
    stream: Optional[Any] = None,
    stream_name: str = "stderr",
    profile: StructuredLogProfile = "compact",
) -> None:
    """为 `scalim.*` 命名空间安装 `JSONL` 日志处理器(幂等)."""
    logger = logging.getLogger(_SCALIM_ROOT_LOGGER_NAME)

    if stream is None:
        normalized_stream_name = _normalize_stream_name(stream_name)
        stream = sys.stdout if normalized_stream_name == "stdout" else sys.stderr

    for handler in logger.handlers:
        if handler.get_name() == _JSONL_HANDLER_NAME:
            return

    handler = logging.StreamHandler(stream=stream)
    handler.name = _JSONL_HANDLER_NAME
    handler.setLevel(logging.NOTSET)
    handler.setFormatter(JsonlFormatter(profile=profile))
    logger.addHandler(handler)
    logger.propagate = False
    if int(logger.level) == logging.NOTSET:
        logger.setLevel(logging.INFO)


def maybe_install_jsonl_logging_from_env() -> None:
    """通过环境变量启用结构化日志(未配置时为无操作)."""
    raw_format = os.environ.get(ENV_SCALIM_LOG_FORMAT, "")
    enabled = False
    fmt = str(raw_format or "").strip().lower()
    if fmt == "jsonl":
        enabled = True
    elif fmt:
        enabled = _normalize_bool_env(fmt)

    if not enabled:
        return

    profile = _normalize_profile(os.environ.get(ENV_SCALIM_LOG_PROFILE, "compact"))
    stream_name = _normalize_stream_name(os.environ.get(ENV_SCALIM_LOG_STREAM, "stderr"))
    install_jsonl_logging(stream_name=stream_name, profile=profile)


def emit_structured(
    logger: logging.Logger,
    *,
    level: int,
    kind: str,
    message: str,
    fields: Optional[Mapping[str, Any]] = None,
    ctx: Optional[Mapping[str, Any]] = None,
    exc_info: Any = None,
) -> None:
    extra: Dict[str, Any] = {
        "scalim_kind": str(kind),
    }
    if fields:
        extra["scalim_fields"] = dict(fields)
    if ctx:
        extra["scalim_ctx"] = dict(ctx)
    logger.log(int(level), "%s", str(message), extra=extra, exc_info=exc_info)


__all__ = (
    "ENV_SCALIM_LOG_FORMAT",
    "ENV_SCALIM_LOG_PROFILE",
    "ENV_SCALIM_LOG_STREAM",
    "StructuredLogProfile",
    "apply_profile",
    "emit_structured",
    "full_to_abbr_key",
    "get_log_context",
    "install_jsonl_logging",
    "is_jsonl_logging_installed",
    "log_context",
    "maybe_install_jsonl_logging_from_env",
    "normalize_keys_to_full",
)
