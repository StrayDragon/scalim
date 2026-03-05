# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any, Optional


def str_or_none(v: Any) -> Optional[str]:
    return str(v) if v is not None else None
