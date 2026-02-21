from collections.abc import Hashable, Iterable

from ....typedefs import FieldValue
from ...context import BatchContext


def build_row(
    context: BatchContext,
    row_id: Hashable,
    field_keys: Iterable[str],
) -> dict[str, FieldValue]:
    row: dict[str, FieldValue] = {}
    for field_key in field_keys:
        row[field_key] = context.get_field_value(field_key, row_id)
    return row


def build_column_data(
    context: BatchContext,
    field_key: str,
    row_ids: Iterable[Hashable],
) -> dict[Hashable, FieldValue]:
    col_data: dict[Hashable, FieldValue] = {}
    for row_id in row_ids:
        col_data[row_id] = context.get_field_value(field_key, row_id)
    return col_data
