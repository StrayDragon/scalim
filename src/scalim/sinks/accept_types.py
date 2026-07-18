"""公开:`sink` 细胞 `accept set` 与 `opt-in` 类型预检."""

from ._internal.accept_types import (
    SinkTypePrecheck,
    ensure_sink_accepted_cell,
    is_csv_accepted_cell,
    is_excel_accepted_cell,
)

__all__ = (
    "SinkTypePrecheck",
    "ensure_sink_accepted_cell",
    "is_csv_accepted_cell",
    "is_excel_accepted_cell",
)
