from typing import Dict, Hashable, Iterable

from ....typedefs import FieldValue
from ...context import BatchContext


def build_row(
    context: BatchContext,
    row_id: Hashable,
    field_keys: Iterable[str],
) -> Dict[str, FieldValue]:
    row: Dict[str, FieldValue] = {}
    for field_key in field_keys:
        row[field_key] = context.get_field_value(field_key, row_id)
    return row


def build_column_data(
    context: BatchContext,
    field_key: str,
    row_ids: Iterable[Hashable],
) -> Dict[Hashable, FieldValue]:
    col_data: Dict[Hashable, FieldValue] = {}
    for row_id in row_ids:
        col_data[row_id] = context.get_field_value(field_key, row_id)
    return col_data


__all__ = ()
