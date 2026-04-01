import logging
from typing import Any, Mapping, Optional

from ..._internal.loggingx import format_kv, prefix


def format_seconds(value: Optional[float], *, digits: int = 3) -> Optional[str]:
    if value is None:
        return None
    fmt = "{:." + str(int(max(0, digits))) + "f}"
    return fmt.format(float(value))


def format_percent(value: Optional[float], *, digits: int = 1) -> Optional[str]:
    if value is None:
        return None
    fmt = "{:." + str(int(max(0, digits))) + "f}%"
    return fmt.format(float(value) * 100.0)


def build_line(subsystem: str, kind: str, mapping: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> str:
    kind_text = str(kind or "").strip()
    if not kind_text:
        raise ValueError

    kv = format_kv(mapping, **kwargs)
    if kv:
        return "{}{} {}".format(prefix(subsystem), kind_text, kv)
    return "{}{}".format(prefix(subsystem), kind_text)


def emit(
    logger: logging.Logger, *, level: int, subsystem: str, kind: str, mapping: Optional[Mapping[str, Any]] = None, **kwargs: Any
) -> None:
    logger.log(int(level), "%s", build_line(subsystem, kind, mapping, **kwargs))


def emit_info(logger: logging.Logger, subsystem: str, kind: str, mapping: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> None:
    emit(logger, level=logging.INFO, subsystem=subsystem, kind=kind, mapping=mapping, **kwargs)


def emit_warning(logger: logging.Logger, subsystem: str, kind: str, mapping: Optional[Mapping[str, Any]] = None, **kwargs: Any) -> None:
    emit(logger, level=logging.WARNING, subsystem=subsystem, kind=kind, mapping=mapping, **kwargs)


__all__ = ()
