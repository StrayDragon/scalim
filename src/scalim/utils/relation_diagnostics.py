from collections.abc import Mapping as MappingABC
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union, cast

from ..spec.ir.relations import FieldRefIr, JoinConditionIr, RelationIr
from ..spec.ir.sources import SourceIr
from ..vendor.compact.typing_extensionsx import override


class TypeMismatchWarning:
    source_a: str
    field_a: str
    source_b: str
    field_b: str
    message: str

    def __init__(
        self,
        source_a: str,
        field_a: str,
        source_b: str,
        field_b: str,
        message: str,
    ) -> None:
        self.source_a = source_a
        self.field_a = field_a
        self.source_b = source_b
        self.field_b = field_b
        self.message = message

    @override
    def __repr__(self) -> str:
        return "TypeMismatchWarning({}.{} <-> {}.{}: {})".format(self.source_a, self.field_a, self.source_b, self.field_b, self.message)


class RelationDiagnostics:
    @staticmethod
    def _extract_field_value(data: Any, field_name: str) -> Any:
        if isinstance(data, MappingABC):
            mapping = cast("Mapping[str, Any]", data)
            return mapping.get(field_name)
        return getattr(data, field_name, None)

    @staticmethod
    def _collect_field_values(data: Any, fields: Tuple[str, ...]) -> Tuple[Tuple[Any, ...], bool]:
        values: List[Any] = []
        missing = False
        for field_name in fields:
            value = RelationDiagnostics._extract_field_value(data, field_name)
            if value is None:
                missing = True
            values.append(value)
        return tuple(values), missing

    @staticmethod
    def _format_value_type(value: Any) -> Union[str, Tuple[str, ...]]:
        if isinstance(value, tuple):
            items = cast("Iterable[Any]", value)
            return tuple(type(item).__name__ if item is not None else "None" for item in items)
        return type(value).__name__ if value is not None else "None"

    @staticmethod
    def _format_field_ref(field_ref: FieldRefIr) -> Tuple[str, str]:
        key_info = ""
        transform_info = ""

        source = field_ref.source
        if isinstance(source, SourceIr):
            if field_ref.field_name == source.key.key:
                key_info = " [KEY]"
            elif field_ref.field_name in source.fk_fields:
                key_info = " [LOOKUP_KEY]"

            if source.key.cast:
                transform_info = " (cast: {})".format(source.key.cast.__name__ if hasattr(source.key.cast, "__name__") else "custom")

        return key_info, transform_info

    @staticmethod
    def _first_complete_key_value(
        sample_data: Dict[Any, Any],
        key_fields: Tuple[str, ...],
    ) -> Optional[Union[Any, Tuple[Any, ...]]]:
        for row in sample_data.values():
            values, missing = RelationDiagnostics._collect_field_values(row, key_fields)
            if missing:
                continue
            return values[0] if len(values) == 1 else values
        return None

    @staticmethod
    def _format_key_fields(key: Union[str, Tuple[str, ...]]) -> Tuple[Tuple[str, ...], str]:
        key_fields = (key,) if isinstance(key, str) else tuple(key)
        if len(key_fields) == 0:
            return key_fields, str(key)
        if len(key_fields) == 1:
            return key_fields, str(key_fields[0])
        return key_fields, ",".join(key_fields)

    @staticmethod
    def _as_tuple(value: Union[Any, Tuple[Any, ...]]) -> Tuple[Any, ...]:
        if isinstance(value, tuple):
            return tuple(cast("Iterable[Any]", value))
        return (value,)

    @staticmethod
    def check_type_compatibility(
        source_a: SourceIr,
        source_b: SourceIr,
        sample_data_a: Optional[Dict[Any, Any]] = None,
        sample_data_b: Optional[Dict[Any, Any]] = None,
    ) -> List[TypeMismatchWarning]:
        warnings: List[TypeMismatchWarning] = []

        key_a = source_a.key.key
        key_b = source_b.key.key

        if not sample_data_a or not sample_data_b:
            return warnings

        key_a_fields, key_a_str = RelationDiagnostics._format_key_fields(key_a)
        key_b_fields, key_b_str = RelationDiagnostics._format_key_fields(key_b)

        sample_value_a = RelationDiagnostics._first_complete_key_value(sample_data_a, key_a_fields)

        sample_value_b = RelationDiagnostics._first_complete_key_value(sample_data_b, key_b_fields)

        if sample_value_a is None or sample_value_b is None:
            return warnings

        values_a = RelationDiagnostics._as_tuple(sample_value_a)
        values_b = RelationDiagnostics._as_tuple(sample_value_b)

        mismatch_found = False
        for idx, (val_a, val_b) in enumerate(zip(values_a, values_b)):
            type_a = type(val_a).__name__
            type_b = type(val_b).__name__
            if type_a == type_b:
                continue
            mismatch_found = True
            field_a = key_a_fields[idx] if idx < len(key_a_fields) else str(key_a)
            field_b = key_b_fields[idx] if idx < len(key_b_fields) else str(key_b)
            warnings.append(
                TypeMismatchWarning(
                    source_a=source_a.source_id,
                    field_a=str(field_a),
                    source_b=source_b.source_id,
                    field_b=str(field_b),
                    message="Key type mismatch: {} vs {}".format(type_a, type_b),
                )
            )

        if mismatch_found and source_a.key.cast is None and source_b.key.cast is None:
            warnings.append(
                TypeMismatchWarning(
                    source_a=source_a.source_id,
                    field_a=key_a_str,
                    source_b=source_b.source_id,
                    field_b=key_b_str,
                    message="Consider adding lookup_cast to normalize key types",
                )
            )

        return warnings

    @staticmethod
    def visualize_path(relation: Union[JoinConditionIr, RelationIr]) -> str:
        lines: List[str] = []
        lines.append("Relation Path:")
        lines.append("-" * 40)

        if isinstance(relation, JoinConditionIr):
            conditions = [relation]
        else:
            conditions = list(relation.conditions)

        for i, cond in enumerate(conditions):
            left = cond.left
            right = cond.right

            left_key_info, left_transform = RelationDiagnostics._format_field_ref(left)
            right_key_info, right_transform = RelationDiagnostics._format_field_ref(right)

            lines.append(
                "  Step {}: {}.{}{}{} == {}.{}{}{}".format(
                    i + 1,
                    left.source.source_id,
                    left.field_name,
                    left_key_info,
                    left_transform,
                    right.source.source_id,
                    right.field_name,
                    right_key_info,
                    right_transform,
                )
            )

        lines.append("-" * 40)
        return "\n".join(lines)

    @staticmethod
    def sample_comparison(  # noqa: C901, PLR0912
        relation: Union[JoinConditionIr, RelationIr],
        data_a: Dict[Any, Any],
        data_b: Dict[Any, Any],
        sample_size: int = 10,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        if isinstance(relation, JoinConditionIr):
            conditions = [relation]
        else:
            conditions = list(relation.conditions)

        if not conditions:
            return results

        left_source = conditions[0].left.source
        right_source = conditions[0].right.source
        left_fields: List[str] = []
        right_fields: List[str] = []

        for cond in conditions:
            if cond.left.source == left_source and cond.right.source == right_source:
                left_fields.append(cond.left.field_name)
                right_fields.append(cond.right.field_name)
            elif cond.right.source == left_source and cond.left.source == right_source:
                left_fields.append(cond.right.field_name)
                right_fields.append(cond.left.field_name)

        left_fields_tuple = tuple(left_fields)

        for count, (key, row) in enumerate(data_a.items()):
            if count >= sample_size:
                break

            fk_values, missing = RelationDiagnostics._collect_field_values(row, left_fields_tuple)
            fk_raw: Union[Any, Tuple[Any, ...]] = fk_values[0] if len(fk_values) == 1 else fk_values
            fk_raw_obj: Any = fk_raw

            normalized_fk: Optional[Any] = None
            if not missing:
                normalized_fk = fk_raw
                if isinstance(right_source, SourceIr) and right_source.key.cast:
                    try:
                        if isinstance(fk_raw, tuple):
                            casted: List[Any] = []
                            for item in cast("Iterable[Any]", fk_raw):
                                converted = right_source.key.cast(item)
                                if converted is None:
                                    casted = []
                                    break
                                casted.append(converted)
                            normalized_fk = tuple(casted) if casted else None
                        else:
                            normalized_fk = right_source.key.cast(fk_raw_obj)
                    except (ValueError, TypeError):
                        normalized_fk = None

            matched = normalized_fk in data_b if normalized_fk is not None else False

            results.append(
                {
                    "key": key,
                    "lookup_key": fk_raw_obj,
                    "lookup_key_type": RelationDiagnostics._format_value_type(fk_raw_obj),
                    "lookup_key_normalized": normalized_fk,
                    "matched": matched,
                    "missing": missing,
                    "target_source": right_source.source_id,
                }
            )

        return results

    @staticmethod
    def format_comparison_table(comparisons: List[Dict[str, Any]]) -> str:
        if not comparisons:
            return "No comparison data"

        lines: List[str] = []
        lines.append("Sample Comparison:")
        lines.append("-" * 80)
        lines.append(
            "{:<10} {:<15} {:<15} {:<20} {:<10} {:<15}".format(
                "Key",
                "Lookup Key",
                "Lookup Key Type",
                "Lookup Key Normalized",
                "Matched",
                "Target",
            )
        )
        lines.append("-" * 80)

        for comp in comparisons:
            lines.append(
                "{:<10} {:<15} {:<15} {:<20} {:<10} {:<15}".format(
                    str(comp["key"])[:10],
                    str(comp["lookup_key"])[:15],
                    str(comp["lookup_key_type"])[:15],
                    str(comp["lookup_key_normalized"])[:20],
                    "Yes" if comp["matched"] else "No",
                    str(comp["target_source"])[:15],
                )
            )

        lines.append("-" * 80)
        return "\n".join(lines)


__all__ = [
    "RelationDiagnostics",
    "TypeMismatchWarning",
]
