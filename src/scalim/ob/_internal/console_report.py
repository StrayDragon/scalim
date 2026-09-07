import logging
from collections.abc import Mapping
from typing import Any

from ..._internal.loggingx import format_kv, prefix


def format_seconds(value: float | None, *, digits: int = 3) -> str | None:
    if value is None:
        return None
    fmt = "{:." + str(int(max(0, digits))) + "f}"
    return fmt.format(float(value))


def format_percent(value: float | None, *, digits: int = 1) -> str | None:
    if value is None:
        return None
    fmt = "{:." + str(int(max(0, digits))) + "f}%"
    return fmt.format(float(value) * 100.0)


def build_line(subsystem: str, kind: str, mapping: Mapping[str, Any] | None = None, **kwargs: Any) -> str:
    kind_text = str(kind or "").strip()
    if not kind_text:
        raise ValueError

    kv = format_kv(mapping, **kwargs)
    if kv:
        return f"{prefix(subsystem)}{kind_text} {kv}"
    return f"{prefix(subsystem)}{kind_text}"


def emit(logger: logging.Logger, *, level: int, subsystem: str, kind: str, mapping: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
    logger.log(int(level), "%s", build_line(subsystem, kind, mapping, **kwargs))


def emit_info(logger: logging.Logger, subsystem: str, kind: str, mapping: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
    emit(logger, level=logging.INFO, subsystem=subsystem, kind=kind, mapping=mapping, **kwargs)


def emit_warning(logger: logging.Logger, subsystem: str, kind: str, mapping: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
    emit(logger, level=logging.WARNING, subsystem=subsystem, kind=kind, mapping=mapping, **kwargs)


__all__ = ()
