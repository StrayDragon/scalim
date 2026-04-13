# pragma: allow-c901-file plan: c60
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, cast

from ......_internal.utils import graph as graph_utils
from ......_internal.utils.iterables import ordered_unique_str
from ......vendor.dataclassesx import dataclass, replace
from ....schema_dsl.models import (
    DEMAND_KEYS,
    OUTPUT_AGGREGATE_KEYS,
    OUTPUT_TARGET_KEYS,
    OUTPUT_TO_KEYS,
    OUTPUT_WRITE_KEYS,
    OutputAggregateConfig,
    OutputAggregateFieldConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
)
from ....schema_dsl.output_enums import (
    AGG_DISTINCT_ON_OVERFLOW_ENUM,
    AGG_RANK_ORDER_ENUM,
    AGG_RANK_TOP_K_MODE_ENUM,
    DEFAULT_AGG_DISTINCT_ON_OVERFLOW,
    DEFAULT_AGG_RANK_ORDER,
    DEFAULT_AGG_RANK_TOP_K_MODE,
    OUTPUT_HEADER_FIELDS_OUTPUT_BY_ENUM,
)
from ....schema_dsl.output_enums import (
    AGG_METRIC_PRODUCER_KEYS as _AGG_FUNC_KEYS,
)
from ....schema_dsl.output_enums import (
    AGG_POST_PRODUCER_KEYS as _POST_FUNC_KEYS,
)
from ....schema_dsl.output_enums import (
    AGG_RANK_PRODUCER_KEYS as _RANK_FUNC_KEYS,
)
from ...validation_contracts import validate_output_name as validate_output_name_ssot
from ..call_by import ScalimCallByParseError, extract_call_by_dependencies, parse_call_by
from ..models import FieldDefIndex, RawDemand
from ..security import (
    ScalimComputeExpressionError,
    ScalimSecurityError,
    SecureComputeEngine,
    build_compute_engine,
    extract_compute_dependencies,
)
from .utils import list_or_none, mapping_or_none, str_or_none


def _non_empty_str(raw: object) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


@dataclass(frozen=True)
class _AggregateFieldDef:
    out_field_id: str
    data: Dict[str, Any]


class _AggregateAliasIndex:
    def __init__(self) -> None:
        self._by_obj_id: Dict[int, str] = {}

    def add(self, data: Dict[str, Any], out_field_id: str) -> None:
        self._by_obj_id[id(data)] = out_field_id

    def get(self, item: Dict[str, Any]) -> Optional[str]:
        return self._by_obj_id.get(id(item))


@dataclass(frozen=True)
class _AggregateFieldIndex:
    field_defs: List[_AggregateFieldDef]
    alias_index: _AggregateAliasIndex


def _resolve_output_targets_from_inheritance(
    base_outputs: List[OutputTargetConfig],
    *,
    validate_output_name: Callable[[str], None],
) -> List[OutputTargetConfig]:
    """阶段 2: 解析 `outputs` 的 `from` 继承(含环检测)."""

    resolver = _OutputFromResolver(base_outputs, validate_output_name=validate_output_name)
    return resolver.resolve_all()


class _OutputFromResolver:
    def __init__(self, base_outputs: List[OutputTargetConfig], *, validate_output_name: Callable[[str], None]) -> None:
        self._by_name: Dict[str, OutputTargetConfig] = {}
        self._ordered_names: List[str] = []
        for t in base_outputs:
            name = str(t.name or "").strip()
            validate_output_name(name)
            if name in self._by_name:
                msg = "Duplicate output name: {}".format(name)
                raise ValueError(msg)
            self._by_name[name] = t
            self._ordered_names.append(name)

        self._resolved: Dict[str, OutputTargetConfig] = {}
        self._visiting: Set[str] = set()

    def resolve_all(self) -> List[OutputTargetConfig]:
        return [self._resolve_one(name) for name in self._ordered_names]

    def _resolve_one(self, name: str) -> OutputTargetConfig:
        existing = self._resolved.get(name)
        if existing is not None:
            return existing
        if name in self._visiting:
            msg = "outputs.*.from has a cycle at '{}'".format(name)
            raise ValueError(msg)
        self._visiting.add(name)
        current = self._by_name[name]

        merged = self._merge_one(current, name=name)
        self._resolved[name] = merged
        self._visiting.remove(name)
        return merged

    def _merge_one(self, current: OutputTargetConfig, *, name: str) -> OutputTargetConfig:
        to = current.to
        write = current.write
        fields = current.fields

        from_name = str(current.from_ or "").strip() or None
        if from_name:
            if from_name not in self._by_name:
                msg = "outputs.{}.from points to unknown output: {}".format(name, from_name)
                raise ValueError(msg)
            base_resolved = self._resolve_one(from_name)
            if to is None:
                to = base_resolved.to
            if write is None:
                write = base_resolved.write
            if current.aggregate is None and fields is None:
                fields = base_resolved.fields
                if fields is None:
                    msg = "outputs.{} inherits fields from '{}', but base output has no fields".format(name, from_name)
                    raise ValueError(msg)

        return replace(current, to=to, write=write, fields=fields)


class ParserOutputsMixin:
    def _build_aggregate_field_index(self, raw_fields: Dict[str, Any]) -> _AggregateFieldIndex:
        field_defs: List[_AggregateFieldDef] = []
        alias_index = _AggregateAliasIndex()
        for out_field_id_raw, field_raw in raw_fields.items():
            out_field_id = str(out_field_id_raw or "").strip()
            if not out_field_id:
                continue
            field_dict = mapping_or_none(field_raw)
            if field_dict is None:
                continue
            field_defs.append(_AggregateFieldDef(out_field_id=out_field_id, data=field_dict))
            alias_index.add(field_dict, out_field_id)
        return _AggregateFieldIndex(field_defs=field_defs, alias_index=alias_index)

    def _resolve_field_ref(
        self,
        item: object,
        *,
        path: str,
        field_def_index: FieldDefIndex,
        agg_field_index: Optional[_AggregateFieldIndex] = None,
    ) -> str:
        if isinstance(item, str):
            return item.strip()

        typed = mapping_or_none(item)
        if typed is None:
            msg = "{} must be field_id string, YAML alias(object), or YAML alias(list)".format(path)
            raise TypeError(msg)

        if agg_field_index is not None:
            out_field_id = agg_field_index.alias_index.get(typed)
            if out_field_id is not None:
                return out_field_id

        direct = field_def_index.alias_index.get(typed)
        if direct is not None:
            return direct.field_id

        # 当 YAML `alias` 的对象 `identity` 丢失(例如 `YAML merge` 产生新对象)时,允许基于内容做兜底匹配(仅唯一匹配时通过).
        matches: List[str] = []
        if agg_field_index is not None:
            matches.extend([fd.out_field_id for fd in agg_field_index.field_defs if fd.data == typed])
        matches.extend([fd.field_id for fd in field_def_index.field_defs if fd.data == typed])

        if not matches:
            msg = "{} cannot resolve object to a unique field_id; prefer string field_id".format(path)
            raise ValueError(msg)

        unique = sorted(set(matches))
        if len(unique) > 1:
            msg = "{} is ambiguous; object matches multiple field_id values: {}. Use string field_id to disambiguate.".format(
                path,
                ", ".join(unique),
            )
            raise ValueError(msg)
        return unique[0]

    def _validate_output_name(self, value: str, *, path: str) -> None:
        validate_output_name_ssot(value, path=str(path))

    def _resolve_output_field_ref(
        self,
        item: object,
        *,
        outputs_key: str,
        output_idx: int,
        field_path: str,
        field_def_index: FieldDefIndex,
    ) -> str:
        path = "{}.{}.fields.{}".format(outputs_key, output_idx, field_path)
        return self._resolve_field_ref(item, path=path, field_def_index=field_def_index)

    def _walk_output_field_items(self, item: object, *, field_path: str) -> List[Tuple[str, object]]:
        nested = list_or_none(item)
        if nested is None:
            return [(field_path, item)]
        out: List[Tuple[str, object]] = []
        for idx, sub in enumerate(nested):
            sub_path = "{}.{}".format(field_path, idx) if field_path else str(idx)
            out.extend(self._walk_output_field_items(sub, field_path=sub_path))
        return out

    def _parse_outputs(
        self,
        raw: RawDemand,
        *,
        field_def_index: FieldDefIndex,
    ) -> Tuple[Tuple[OutputTargetConfig, ...], Optional[List[str]]]:
        outputs_key = DEMAND_KEYS["outputs"]
        outputs_val = raw.data.get(outputs_key)

        outputs_list = list_or_none(outputs_val)
        if outputs_val is not None and outputs_list is None:
            msg = "{} must be a list".format(outputs_key)
            raise TypeError(msg)
        if not outputs_list:
            return (), None

        known_field_ids = set(field_def_index.defs_by_id.keys())
        engine = build_compute_engine()

        base_outputs: List[OutputTargetConfig] = []
        for idx, item in enumerate(outputs_list):
            item_dict = mapping_or_none(item)
            if item_dict is None:
                msg = "{}.{} must be an object".format(outputs_key, idx)
                raise TypeError(msg)
            base_outputs.append(
                self._parse_output_target(
                    item_dict,
                    idx=idx,
                    outputs_key=outputs_key,
                    field_def_index=field_def_index,
                    known_field_ids=known_field_ids,
                    engine=engine,
                )
            )

        resolved_outputs = _resolve_output_targets_from_inheritance(
            base_outputs,
            validate_output_name=lambda x: self._validate_output_name(x, path="outputs.*.name"),
        )
        self._validate_outputs_semantics(resolved_outputs, known_field_ids=known_field_ids)

        required_field_ids = self._collect_required_field_ids_from_outputs(resolved_outputs)
        return tuple(resolved_outputs), required_field_ids

    def _parse_output_target(  # noqa: C901
        self,
        raw_target: Dict[str, Any],
        *,
        idx: int,
        outputs_key: str,
        field_def_index: FieldDefIndex,
        known_field_ids: Set[str],
        engine: SecureComputeEngine,
    ) -> OutputTargetConfig:
        name = _non_empty_str(raw_target.get(OUTPUT_TARGET_KEYS["name"]))
        self._validate_output_name(name, path="{}.{}.name".format(outputs_key, idx))
        from_name = str_or_none(raw_target.get(OUTPUT_TARGET_KEYS["from_"]))
        from_name = _non_empty_str(from_name) or None
        if from_name:
            self._validate_output_name(from_name, path="{}.{}.from".format(outputs_key, idx))

        if "container" in raw_target:
            msg = (
                "{}.{}.container was removed; migrate CSV outputs to resources.files + outputs[*].to.file + outputs[*].write, "
                "and .xlsx outputs to resources.books + outputs[*].to.book / outputs[*].to.sheet + outputs[*].write"
            ).format(outputs_key, idx)
            raise ValueError(msg)

        to_raw = mapping_or_none(raw_target.get(OUTPUT_TARGET_KEYS["to"]))
        to_cfg = self._parse_output_to(to_raw) if to_raw else None

        write_raw = mapping_or_none(raw_target.get(OUTPUT_TARGET_KEYS["write"]))
        write_cfg = self._parse_output_write(write_raw, base_path="{}.{}.write".format(outputs_key, idx)) if write_raw else None

        where = str_or_none(raw_target.get(OUTPUT_TARGET_KEYS["where"]))
        where = _non_empty_str(where) or None
        requires = self._parse_where_requires(
            where,
            output_name=name,
            known_field_ids=known_field_ids,
            engine=engine,
            path="{}.{}.where".format(outputs_key, idx),
        )

        agg_raw = mapping_or_none(raw_target.get(OUTPUT_TARGET_KEYS["aggregate"]))
        agg_field_index = None
        if agg_raw is not None:
            raw_agg_fields = mapping_or_none(agg_raw.get(OUTPUT_AGGREGATE_KEYS["fields"]))
            if raw_agg_fields is not None:
                agg_field_index = self._build_aggregate_field_index(raw_agg_fields)
        aggregate = (
            self._parse_output_aggregate(
                agg_raw,
                base_path="{}.{}.aggregate".format(outputs_key, idx),
                field_def_index=field_def_index,
                engine=engine,
            )
            if agg_raw
            else None
        )

        fields_raw = raw_target.get(OUTPUT_TARGET_KEYS["fields"])
        fields_list = list_or_none(fields_raw)
        if fields_raw is not None and fields_list is None:
            msg = "{}.{}.fields must be a list".format(outputs_key, idx)
            raise TypeError(msg)
        fields: Optional[Tuple[str, ...]] = None
        if fields_list is not None:
            normalized_fields: List[str] = []
            flattened: List[Tuple[str, object]] = []
            for outer_idx, field_item in enumerate(fields_list):
                flattened.extend(self._walk_output_field_items(field_item, field_path=str(outer_idx)))
            for field_path, field_item in flattened:
                if aggregate is None:
                    field_id = self._resolve_output_field_ref(
                        field_item,
                        outputs_key=outputs_key,
                        output_idx=idx,
                        field_path=field_path,
                        field_def_index=field_def_index,
                    )
                else:
                    path = "{}.{}.fields.{}".format(outputs_key, idx, field_path)
                    field_id = self._resolve_field_ref(
                        field_item,
                        path=path,
                        field_def_index=field_def_index,
                        agg_field_index=agg_field_index,
                    )
                if field_id:
                    normalized_fields.append(field_id)
            fields = tuple(normalized_fields) if normalized_fields else ()

        return OutputTargetConfig(
            name=name,
            from_=from_name,
            to=to_cfg,
            write=write_cfg,
            fields=fields,
            where=where,
            aggregate=aggregate,
            requires=requires,
        )

    def _parse_output_to(self, raw: Dict[str, Any]) -> OutputToConfig:
        file_id = str_or_none(raw.get(OUTPUT_TO_KEYS["file"]))
        file_id = _non_empty_str(file_id) or None
        book = str_or_none(raw.get(OUTPUT_TO_KEYS["book"]))
        book = _non_empty_str(book) or None
        sheet = str_or_none(raw.get(OUTPUT_TO_KEYS["sheet"]))
        sheet = _non_empty_str(sheet) or None
        return OutputToConfig(file=file_id, book=book, sheet=sheet)

    def _parse_output_write(self, raw: Dict[str, Any], *, base_path: str) -> OutputWriteConfig:
        include_header_raw = raw.get(OUTPUT_WRITE_KEYS["include_header"])
        include_header = None
        if include_header_raw is not None:
            if not isinstance(include_header_raw, bool):
                msg = "{}.include_header must be a boolean".format(base_path)
                raise TypeError(msg)
            include_header = bool(include_header_raw)

        header_fields_output_by = str_or_none(raw.get(OUTPUT_WRITE_KEYS["header_fields_output_by"]))
        header_fields_output_by = _non_empty_str(header_fields_output_by) or None
        if header_fields_output_by is not None and header_fields_output_by not in OUTPUT_HEADER_FIELDS_OUTPUT_BY_ENUM:
            msg = "{}.header_fields_output_by={!r} is invalid; expected one of: {}".format(
                base_path, header_fields_output_by, ", ".join(OUTPUT_HEADER_FIELDS_OUTPUT_BY_ENUM)
            )
            raise ValueError(msg)

        removed: Tuple[Tuple[str, str], ...] = (
            ("mode", "resources.books.*.write_defaults.mode"),
            ("align_by", "resources.books.*.write_defaults.align_by"),
            ("header_policy", "resources.books.*.write_defaults.header_policy"),
            ("on_mismatch", "resources.books.*.write_defaults.on_mismatch"),
            ("on_conflict", "resources.books.*.write_defaults.on_conflict"),
        )
        for key, hint in removed:
            if key not in raw:
                continue
            msg = "{}.{} was moved out of outputs[*].write. Hint: configure it via {}.".format(base_path, key, hint)
            raise ValueError(msg)

        return OutputWriteConfig(include_header=include_header, header_fields_output_by=header_fields_output_by)

    def _parse_output_aggregate(  # noqa: C901, PLR0912
        self,
        raw: Dict[str, Any],
        *,
        base_path: str,
        field_def_index: FieldDefIndex,
        engine: SecureComputeEngine,
    ) -> OutputAggregateConfig:
        if "metrics" in raw:
            msg = "{}.metrics was removed; use {}.fields".format(base_path, base_path)
            raise ValueError(msg)
        for legacy in ("rank_by", "rank_field_id", "rank_order", "top_k"):
            if legacy in raw:
                msg = "{}.{} was removed; declare rank as a field under {}.fields".format(base_path, legacy, base_path)
                raise ValueError(msg)

        group_by_raw = raw.get(OUTPUT_AGGREGATE_KEYS["group_by"])
        group_by_list = list_or_none(group_by_raw)
        if group_by_list is None:
            msg = "{}.group_by must be a list".format(base_path)
            raise TypeError(msg)
        group_by: List[str] = []
        for outer_idx, field_item in enumerate(group_by_list):
            flattened = self._walk_output_field_items(field_item, field_path=str(outer_idx))
            for field_path, leaf in flattened:
                field_id = self._resolve_field_ref(
                    leaf,
                    path="{}.group_by.{}".format(base_path, field_path),
                    field_def_index=field_def_index,
                )
                if field_id:
                    group_by.append(field_id)
        group_by_t = tuple(group_by)

        fields_raw = mapping_or_none(raw.get(OUTPUT_AGGREGATE_KEYS["fields"]))
        if fields_raw is None:
            msg = "{}.fields must be an object".format(base_path)
            raise TypeError(msg)
        agg_field_index = self._build_aggregate_field_index(fields_raw)
        fields: Dict[str, OutputAggregateFieldConfig] = {}
        for out_field_id_raw, field_raw in fields_raw.items():
            out_field_id = str(out_field_id_raw or "").strip()
            if not out_field_id:
                continue
            fields[out_field_id] = self._parse_output_aggregate_field(
                field_raw,
                base_path="{}.fields.{}".format(base_path, out_field_id),
                field_def_index=field_def_index,
                agg_field_index=agg_field_index,
                engine=engine,
            )

        max_groups = int(raw.get(OUTPUT_AGGREGATE_KEYS["max_groups"], 0) or 0)
        if max_groups < 0:
            msg = "{}.max_groups must be >= 0".format(base_path)
            raise ValueError(msg)
        max_distinct = int(raw.get(OUTPUT_AGGREGATE_KEYS["max_distinct"], 0) or 0)
        if max_distinct < 0:
            msg = "{}.max_distinct must be >= 0".format(base_path)
            raise ValueError(msg)

        distinct_on_overflow = str(
            raw.get(
                OUTPUT_AGGREGATE_KEYS["distinct_on_overflow"],
                DEFAULT_AGG_DISTINCT_ON_OVERFLOW,
            )
            or DEFAULT_AGG_DISTINCT_ON_OVERFLOW
        ).lower()
        if distinct_on_overflow not in AGG_DISTINCT_ON_OVERFLOW_ENUM:
            msg = "{}.distinct_on_overflow={!r} is invalid; expected one of: {}".format(
                base_path,
                distinct_on_overflow,
                ", ".join(AGG_DISTINCT_ON_OVERFLOW_ENUM),
            )
            raise ValueError(msg)

        return OutputAggregateConfig(
            group_by=group_by_t,
            fields=fields,
            max_groups=max_groups,
            max_distinct=max_distinct,
            distinct_on_overflow=distinct_on_overflow,
        )

    def _parse_output_aggregate_field(  # noqa: C901, PLR0912
        self,
        raw: object,
        *,
        base_path: str,
        field_def_index: FieldDefIndex,
        agg_field_index: _AggregateFieldIndex,
        engine: SecureComputeEngine,
    ) -> OutputAggregateFieldConfig:
        typed = mapping_or_none(raw)
        if typed is None:
            msg = "{} must be an object".format(base_path)
            raise TypeError(msg)
        if not typed:
            msg = "{} must not be empty".format(base_path)
            raise ValueError(msg)

        display_name = ""
        if "name" in typed:
            name_raw = typed.get("name")
            if name_raw is not None and not isinstance(name_raw, str):
                msg = "{}.name must be a string".format(base_path)
                raise TypeError(msg)
            display_name = _non_empty_str(name_raw) if name_raw is not None else ""

        normalized: List[Tuple[str, object]] = []
        for k, v in typed.items():
            key = str(k or "").strip()
            if not key:
                continue
            if key == "name":
                continue
            normalized.append((key, v))

        if not normalized:
            msg = "{} must not be empty".format(base_path)
            raise ValueError(msg)
        if len(normalized) != 1:
            keys = ", ".join(sorted({k for k, _ in normalized}))
            msg = "{} must contain exactly 1 producer key, got: {}".format(base_path, keys)
            raise ValueError(msg)

        producer_key, producer_value = normalized[0]
        if producer_key in _AGG_FUNC_KEYS:
            cfg = self._parse_output_aggregate_field_agg(
                producer_key,
                producer_value,
                base_path=base_path,
                field_def_index=field_def_index,
            )
        elif producer_key in _RANK_FUNC_KEYS:
            cfg = self._parse_output_aggregate_field_rank(
                producer_key,
                producer_value,
                base_path=base_path,
                field_def_index=field_def_index,
                agg_field_index=agg_field_index,
            )
        elif producer_key == "call_by":
            cfg = self._parse_output_aggregate_field_call_by(producer_value, base_path=base_path)
        elif producer_key == "score_by_rank":
            cfg = self._parse_output_aggregate_field_score_by_rank(
                producer_value,
                base_path=base_path,
                field_def_index=field_def_index,
                agg_field_index=agg_field_index,
            )
        elif producer_key == "compute":
            cfg = self._parse_output_aggregate_field_compute(
                producer_value,
                base_path=base_path,
                engine=engine,
            )
        else:
            allowed = ", ".join(list(_AGG_FUNC_KEYS) + list(_RANK_FUNC_KEYS) + list(_POST_FUNC_KEYS))
            msg = "{} has unknown producer key {!r}; expected one of: {}".format(base_path, producer_key, allowed)
            raise ValueError(msg)

        return OutputAggregateFieldConfig(producer_key=producer_key, config=cfg, name=display_name)

    def _parse_output_aggregate_field_agg(  # noqa: C901, PLR0912, PLR0915
        self,
        producer_key: str,
        raw: object,
        *,
        base_path: str,
        field_def_index: FieldDefIndex,
    ) -> Dict[str, Any]:
        args = mapping_or_none(raw)
        if args is None:
            msg = "{}.{} must be an object".format(base_path, producer_key)
            raise TypeError(msg)

        allowed_keys: Tuple[str, ...] = ()
        required_keys: Tuple[str, ...] = ()

        if producer_key == "count":
            allowed_keys = ("field",)
        elif producer_key in ("sum", "min", "max", "count_true"):
            allowed_keys = ("field",)
            required_keys = ("field",)
        elif producer_key == "count_true_gte":
            allowed_keys = ("field", "threshold")
            required_keys = ("field", "threshold")
        elif producer_key == "count_distinct":
            allowed_keys = ("field", "fields")
        else:  # pragma: no cover  # pragma: allow-no-cover producer_key validated by caller dispatch
            msg = "Unknown agg producer_key: {!r}".format(producer_key)
            raise ValueError(msg)

        unknown = sorted({str(k) for k in args} - set(allowed_keys))
        if unknown:
            msg = "{}.{} has unknown keys: {}".format(base_path, producer_key, ", ".join(unknown))
            raise ValueError(msg)

        out: Dict[str, Any] = {}
        if "field" in args:
            raw_field = args.get("field")
            if raw_field is None:
                out["field"] = None
            else:
                field_id = self._resolve_field_ref(
                    raw_field,
                    path="{}.{}.field".format(base_path, producer_key),
                    field_def_index=field_def_index,
                )
                out["field"] = field_id or None
        if "fields" in args:
            raw_fields = args.get("fields")
            fields_list = list_or_none(raw_fields)
            if raw_fields is not None and fields_list is None:
                msg = "{}.{}.fields must be a list".format(base_path, producer_key)
                raise TypeError(msg)
            if fields_list is not None:
                normalized_fields: List[str] = []
                for outer_idx, field_item in enumerate(fields_list):
                    flattened = self._walk_output_field_items(field_item, field_path=str(outer_idx))
                    for field_path, leaf in flattened:
                        fid = self._resolve_field_ref(
                            leaf,
                            path="{}.{}.fields.{}".format(base_path, producer_key, field_path),
                            field_def_index=field_def_index,
                        )
                        if fid:
                            normalized_fields.append(fid)
                out["fields"] = tuple(normalized_fields) if normalized_fields else ()

        if required_keys:
            for k in required_keys:
                if k == "threshold":
                    if args.get("threshold") is None:
                        msg = "{}.{}.threshold is required".format(base_path, producer_key)
                        raise ValueError(msg)
                    out["threshold"] = args.get("threshold")
                    continue
                if k == "field" and not out.get("field"):
                    msg = "{}.{}.field is required".format(base_path, producer_key)
                    raise ValueError(msg)

        if producer_key == "count_distinct":
            field_id = out.get("field")
            field_ids = out.get("fields")
            if field_id and field_ids:
                msg = "{}.count_distinct does not allow both field and fields".format(base_path)
                raise ValueError(msg)
            if not field_id and not field_ids:
                msg = "{}.count_distinct requires field or fields".format(base_path)
                raise ValueError(msg)
            if field_ids is not None and not field_ids:
                msg = "{}.count_distinct.fields must not be empty".format(base_path)
                raise ValueError(msg)

        return out

    def _parse_output_aggregate_field_rank(  # noqa: C901, PLR0912, PLR0915
        self,
        producer_key: str,
        raw: object,
        *,
        base_path: str,
        field_def_index: FieldDefIndex,
        agg_field_index: _AggregateFieldIndex,
    ) -> Dict[str, Any]:
        args = mapping_or_none(raw)
        if args is None:
            msg = "{}.{} must be an object".format(base_path, producer_key)
            raise TypeError(msg)

        allowed_keys = ("by", "partition_by", "order", "order_by", "top_k", "top_k_mode")
        unknown = sorted({str(k) for k in args} - set(allowed_keys))
        if unknown:
            msg = "{}.{} has unknown keys: {}".format(base_path, producer_key, ", ".join(unknown))
            raise ValueError(msg)

        raw_by = args.get("by")
        if raw_by is None:
            msg = "{}.{}.by is required".format(base_path, producer_key)
            raise ValueError(msg)
        by = self._resolve_field_ref(
            raw_by,
            path="{}.{}.by".format(base_path, producer_key),
            field_def_index=field_def_index,
            agg_field_index=agg_field_index,
        )
        if not by:
            msg = "{}.{}.by is required".format(base_path, producer_key)
            raise ValueError(msg)

        partition_by_list = list_or_none(args.get("partition_by"))
        if args.get("partition_by") is not None and partition_by_list is None:
            msg = "{}.{}.partition_by must be a list".format(base_path, producer_key)
            raise TypeError(msg)
        partition_by: Tuple[str, ...] = ()
        if partition_by_list is not None:
            normalized_partition_by: List[str] = []
            for outer_idx, part_item in enumerate(partition_by_list):
                flattened = self._walk_output_field_items(part_item, field_path=str(outer_idx))
                for field_path, leaf in flattened:
                    fid = self._resolve_field_ref(
                        leaf,
                        path="{}.{}.partition_by.{}".format(base_path, producer_key, field_path),
                        field_def_index=field_def_index,
                    )
                    if fid:
                        normalized_partition_by.append(fid)
            if not normalized_partition_by:
                msg = "{}.{}.partition_by must not be empty".format(base_path, producer_key)
                raise ValueError(msg)
            partition_by = tuple(normalized_partition_by)

        order = str(args.get("order") or DEFAULT_AGG_RANK_ORDER).lower()
        if order not in AGG_RANK_ORDER_ENUM:
            msg = "{}.{}.order={!r} is invalid; expected one of: {}".format(base_path, producer_key, order, ", ".join(AGG_RANK_ORDER_ENUM))
            raise ValueError(msg)

        order_by_list = list_or_none(args.get("order_by"))
        if args.get("order_by") is not None and order_by_list is None:
            msg = "{}.{}.order_by must be a list".format(base_path, producer_key)
            raise TypeError(msg)
        order_by: Tuple[str, ...] = ()
        if order_by_list is not None:
            normalized_order_by: List[str] = []
            for outer_idx, order_item in enumerate(order_by_list):
                flattened = self._walk_output_field_items(order_item, field_path=str(outer_idx))
                for field_path, leaf in flattened:
                    fid = self._resolve_field_ref(
                        leaf,
                        path="{}.{}.order_by.{}".format(base_path, producer_key, field_path),
                        field_def_index=field_def_index,
                        agg_field_index=agg_field_index,
                    )
                    if fid:
                        normalized_order_by.append(fid)
            if not normalized_order_by:
                msg = "{}.{}.order_by must not be empty".format(base_path, producer_key)
                raise ValueError(msg)
            order_by = tuple(normalized_order_by)

        top_k = int(args.get("top_k", 0) or 0)
        if top_k < 0:
            msg = "{}.{}.top_k must be >= 0".format(base_path, producer_key)
            raise ValueError(msg)

        top_k_mode = str(args.get("top_k_mode") or DEFAULT_AGG_RANK_TOP_K_MODE).lower()
        if top_k_mode not in AGG_RANK_TOP_K_MODE_ENUM:
            msg = "{}.{}.top_k_mode={!r} is invalid; expected one of: {}".format(
                base_path,
                producer_key,
                top_k_mode,
                ", ".join(AGG_RANK_TOP_K_MODE_ENUM),
            )
            raise ValueError(msg)

        return {
            "by": by,
            "partition_by": partition_by,
            "order": order,
            "order_by": order_by,
            "top_k": top_k,
            "top_k_mode": top_k_mode,
        }

    def _parse_output_aggregate_field_call_by(self, raw: object, *, base_path: str) -> str:
        if not isinstance(raw, str):
            msg = "{}.call_by must be a string".format(base_path)
            raise TypeError(msg)
        call_by = raw.strip()
        if not call_by:
            msg = "{}.call_by must not be empty".format(base_path)
            raise ValueError(msg)
        try:
            _ = parse_call_by(call_by)
        except ScalimCallByParseError as exc:
            msg = "{}.call_by is invalid: {}".format(base_path, exc)
            raise ValueError(msg) from exc
        return call_by

    def _parse_output_aggregate_field_compute(self, raw: object, *, base_path: str, engine: SecureComputeEngine) -> Dict[str, Any]:
        if not isinstance(raw, str):
            msg = "{}.compute must be a string".format(base_path)
            raise TypeError(msg)
        expr = str(raw or "").strip()
        if not expr:
            msg = "{}.compute must not be empty".format(base_path)
            raise ValueError(msg)

        deps = tuple(str(x) for x in extract_compute_dependencies(expr))
        try:
            _ = engine.compile(expr, deps)
        except (ScalimComputeExpressionError, ScalimSecurityError) as exc:
            msg = "{}.compute is invalid: {}".format(base_path, exc)
            raise ValueError(msg) from exc

        return {"expression": expr, "dependencies": deps}

    def _parse_output_aggregate_field_score_by_rank(
        self,
        raw: object,
        *,
        base_path: str,
        field_def_index: FieldDefIndex,
        agg_field_index: _AggregateFieldIndex,
    ) -> Dict[str, Any]:
        args = mapping_or_none(raw)
        if args is None:
            msg = "{}.score_by_rank must be an object".format(base_path)
            raise TypeError(msg)
        allowed_keys = ("rank_field", "base", "step")
        unknown = sorted({str(k) for k in args} - set(allowed_keys))
        if unknown:
            msg = "{}.score_by_rank has unknown keys: {}".format(base_path, ", ".join(unknown))
            raise ValueError(msg)
        rank_field = None
        if "rank_field" in args:
            rank_field_raw = args.get("rank_field")
            if rank_field_raw is not None:
                rank_field = self._resolve_field_ref(
                    rank_field_raw,
                    path="{}.score_by_rank.rank_field".format(base_path),
                    field_def_index=field_def_index,
                    agg_field_index=agg_field_index,
                )
                rank_field = _non_empty_str(rank_field) or None
        return {
            "rank_field": rank_field,
            "base": args.get("base"),
            "step": args.get("step"),
        }

    def _parse_where_requires(
        self,
        expr: Optional[str],
        *,
        output_name: str,
        known_field_ids: Set[str],
        engine: SecureComputeEngine,
        path: str,
    ) -> Tuple[str, ...]:
        if expr is None:
            return ()
        expr = str(expr).strip()
        if not expr:
            return ()

        deps = tuple(str(x) for x in extract_compute_dependencies(expr))

        missing = [d for d in deps if d not in known_field_ids]
        if missing:
            msg = "Output '{}' where depends on unknown fields: {}".format(output_name or "(unknown)", ", ".join(sorted(missing)))
            raise ValueError(msg)

        try:
            _ = engine.compile(expr, deps)
        except (ScalimComputeExpressionError, ScalimSecurityError) as exc:
            msg = "Invalid where expression at {}: {}".format(path, exc)
            raise ValueError(msg) from exc
        return deps

    def _validate_output_binding_semantics(self, t: OutputTargetConfig, *, idx: int) -> None:
        to_cfg = t.to
        if to_cfg is None:
            msg = "outputs.{}.to is required; declare exactly one of to.file or to.book".format(int(idx))
            raise ValueError(msg)

        file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
        book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
        sheet_name = str(to_cfg.sheet or "").strip() if to_cfg.sheet is not None else ""

        if bool(file_id) == bool(book_id):
            msg = "outputs.{}.to must declare exactly one of to.file or to.book".format(int(idx))
            raise ValueError(msg)

        if sheet_name and not book_id:
            msg = "outputs.{}.to.sheet requires outputs.{}.to.book".format(int(idx), int(idx))
            raise ValueError(msg)

        write_cfg = t.write
        if write_cfg is None:
            return

    def _validate_detail_output_semantics(self, t: OutputTargetConfig, name: str, known_field_ids: Set[str]) -> None:
        if t.fields is None or not t.fields:
            msg = "outputs.{} requires fields for detail output".format(name)
            raise ValueError(msg)
        unknown_fields = [fid for fid in t.fields if fid not in known_field_ids]
        if unknown_fields:
            msg = "outputs.{}.fields reference unknown fields: {}".format(name, ", ".join(sorted(set(unknown_fields))))
            raise ValueError(msg)

    def _validate_aggregate_group_and_metrics(
        self,
        t: OutputTargetConfig,
        name: str,
        known_field_ids: Set[str],
        agg: OutputAggregateConfig,
    ) -> Tuple[List[str], List[str], Set[str]]:
        if not agg.group_by:
            msg = "outputs.{}.aggregate.group_by cannot be empty".format(name)
            raise ValueError(msg)
        if not agg.fields:
            msg = "outputs.{}.aggregate.fields cannot be empty".format(name)
            raise ValueError(msg)

        agg_field_ids = set(agg.fields.keys())
        overlap = [fid for fid in agg.group_by if fid in agg_field_ids]
        if overlap:
            msg = "outputs.{}.aggregate.fields ids conflict with group_by fields: {}".format(name, ", ".join(sorted(set(overlap))))
            raise ValueError(msg)
        missing = [fid for fid in agg.group_by if fid not in known_field_ids]
        if missing:
            msg = "outputs.{}.aggregate.group_by reference unknown fields: {}".format(name, ", ".join(sorted(set(missing))))
            raise ValueError(msg)

        metric_field_ids = sorted([fid for fid, cfg in agg.fields.items() if cfg.producer_key in _AGG_FUNC_KEYS])
        if not metric_field_ids:
            msg = "outputs.{}.aggregate.fields must include at least one aggregation function field".format(name)
            raise ValueError(msg)

        rank_field_ids = sorted([fid for fid, cfg in agg.fields.items() if cfg.producer_key in _RANK_FUNC_KEYS])
        post_field_ids = sorted([fid for fid, cfg in agg.fields.items() if cfg.producer_key in _POST_FUNC_KEYS])

        metric_required = self._collect_required_field_ids_from_aggregate(agg)
        missing = [fid for fid in metric_required if fid not in known_field_ids]
        if missing:
            msg = "outputs.{}.aggregate.fields reference unknown input fields: {}".format(name, ", ".join(sorted(set(missing))))
            raise ValueError(msg)

        # 排名/派生字段允许引用 `aggregate.group_by` + `aggregate.fields` 任意字段(含派生字段).
        allowed_agg_out_fields = set(agg.group_by) | set(agg_field_ids)

        if t.fields is not None:
            if not t.fields:
                msg = "outputs.{}.fields must not be empty".format(name)
                raise ValueError(msg)
            allowed_layout_fields = set(agg.group_by) | set(agg_field_ids)
            unknown_layout_fields = [fid for fid in t.fields if fid not in allowed_layout_fields]
            if unknown_layout_fields:
                msg = "outputs.{}.fields reference unknown aggregate output fields: {}".format(
                    name, ", ".join(sorted(set(unknown_layout_fields)))
                )
                raise ValueError(msg)

        return rank_field_ids, post_field_ids, allowed_agg_out_fields

    def _validate_rank_semantics(
        self,
        name: str,
        agg: OutputAggregateConfig,
        rank_field_ids: List[str],
        allowed_agg_out_fields: Set[str],
    ) -> None:
        rank_with_top_k: List[str] = []
        for fid in rank_field_ids:
            cfg = agg.fields[fid]
            rank_cfg = cast("Dict[str, Any]", cfg.config)  # pragma: allow-cast output aggregate config typed narrowing
            by = str(rank_cfg.get("by") or "").strip()
            if by not in allowed_agg_out_fields:
                msg = "outputs.{}.aggregate.fields.{}.{} by={!r} must reference group_by fields or aggregate.fields ids: {}".format(
                    name,
                    fid,
                    cfg.producer_key,
                    by,
                    ", ".join(sorted(allowed_agg_out_fields)),
                )
                raise ValueError(msg)

            partition_by = cast(
                "Tuple[str, ...]", rank_cfg.get("partition_by") or ()
            )  # pragma: allow-cast output aggregate config typed narrowing
            missing = [x for x in partition_by if x not in agg.group_by]
            if missing:
                msg = "outputs.{}.aggregate.fields.{}.{} partition_by must be a subset of group_by: {}".format(
                    name,
                    fid,
                    cfg.producer_key,
                    ", ".join(sorted(set(missing))),
                )
                raise ValueError(msg)

            order_by = cast("Tuple[str, ...]", rank_cfg.get("order_by") or ())  # pragma: allow-cast output aggregate config typed narrowing
            missing = [x for x in order_by if x not in allowed_agg_out_fields]
            if missing:
                msg = "outputs.{}.aggregate.fields.{}.{} order_by reference unknown agg output fields: {}".format(
                    name,
                    fid,
                    cfg.producer_key,
                    ", ".join(sorted(set(missing))),
                )
                raise ValueError(msg)

            top_k = int(rank_cfg.get("top_k") or 0)
            if top_k and str(rank_cfg.get("top_k_mode") or "rank").lower() == "rows" and not order_by:
                msg = "outputs.{}.aggregate.fields.{}.{} top_k_mode='rows' requires order_by".format(
                    name,
                    fid,
                    cfg.producer_key,
                )
                raise ValueError(msg)

            if top_k:
                rank_with_top_k.append(fid)

        if len(rank_with_top_k) > 1:
            msg = "outputs.{}.aggregate supports top_k on at most one rank field; got: {}".format(
                name,
                ", ".join(sorted(rank_with_top_k)),
            )
            raise ValueError(msg)

    def _validate_aggregate_post_semantics(
        self,
        name: str,
        agg: OutputAggregateConfig,
        agg_field_ids: Set[str],
        rank_field_ids: List[str],
        post_field_ids: List[str],
    ) -> None:
        allowed = set(agg.group_by) | set(agg_field_ids)
        for fid in post_field_ids:
            cfg = agg.fields[fid]
            if cfg.producer_key == "score_by_rank":
                score_cfg = cast("Dict[str, Any]", cfg.config)  # pragma: allow-cast output aggregate config typed narrowing
                rank_field = str(score_cfg.get("rank_field") or "rank").strip()
                if rank_field not in rank_field_ids:
                    msg = "outputs.{}.aggregate.fields.{}.score_by_rank rank_field={!r} must reference a rank field id: {}".format(
                        name,
                        fid,
                        rank_field,
                        ", ".join(sorted(rank_field_ids)),
                    )
                    raise ValueError(msg)
                continue

            if cfg.producer_key == "call_by":
                call_by = str(cfg.config or "").strip()
                deps = extract_call_by_dependencies(call_by)
                missing = [d for d in deps if d not in allowed]
                if missing:
                    msg = "outputs.{}.aggregate.fields.{}.call_by reference unknown fields: {}".format(
                        name,
                        fid,
                        ", ".join(sorted(set(missing))),
                    )
                    raise ValueError(msg)
                continue

            # `post_field_ids` 已按 `_POST_FUNC_KEYS` 过滤; 走到这里时 `producer_key` 只能是 `compute`.
            compute_cfg = cast("Dict[str, Any]", cfg.config)  # pragma: allow-cast output aggregate config typed narrowing
            compute_deps = cast(
                "Tuple[str, ...]", compute_cfg.get("dependencies") or ()
            )  # pragma: allow-cast output aggregate config typed narrowing
            missing = [d for d in compute_deps if d not in allowed]
            if missing:
                msg = "outputs.{}.aggregate.fields.{}.compute reference unknown fields: {}".format(
                    name,
                    fid,
                    ", ".join(sorted(set(missing))),
                )
                raise ValueError(msg)

    def _derived_deps_for_aggregate_derived_field(self, cfg: OutputAggregateFieldConfig) -> Tuple[str, ...]:
        producer_key = str(cfg.producer_key)
        if producer_key in _RANK_FUNC_KEYS:
            rank_cfg = cast("Dict[str, Any]", cfg.config)  # pragma: allow-cast output aggregate config typed narrowing
            by = str(rank_cfg.get("by") or "").strip()
            order_by = cast("Tuple[str, ...]", rank_cfg.get("order_by") or ())  # pragma: allow-cast output aggregate config typed narrowing
            deps_list = [by] + [str(x) for x in order_by]
            # `order_by` 缺省时,语义等价于 `[by]`.
            return ordered_unique_str([x for x in deps_list if x])

        if producer_key == "score_by_rank":
            score_cfg = cast("Dict[str, Any]", cfg.config)  # pragma: allow-cast output aggregate config typed narrowing
            rf = str(score_cfg.get("rank_field") or "rank").strip() or "rank"
            return (rf,)

        if producer_key == "call_by":
            call_by = str(cfg.config or "").strip()
            return tuple(str(x) for x in extract_call_by_dependencies(call_by))

        if producer_key == "compute":
            compute_cfg = cast("Dict[str, Any]", cfg.config)  # pragma: allow-cast output aggregate config typed narrowing
            return cast(
                "Tuple[str, ...]", compute_cfg.get("dependencies") or ()
            )  # pragma: allow-cast output aggregate config typed narrowing

        return ()

    def _validate_aggregate_derived_dag(
        self,
        name: str,
        agg: OutputAggregateConfig,
        rank_field_ids: List[str],
        post_field_ids: List[str],
    ) -> None:
        # 依赖 `DAG`: 检测循环依赖并给出可操作错误.
        derived_ids = set(rank_field_ids) | set(post_field_ids)
        if not derived_ids:
            return
        deps_by_id: Dict[str, Tuple[str, ...]] = {}
        for fid in derived_ids:
            cfg = agg.fields[fid]
            deps_by_id[fid] = self._derived_deps_for_aggregate_derived_field(cfg)

        def _get_derived_deps(
            node_id: str,
            deps_map: Dict[str, Tuple[str, ...]] = deps_by_id,
            node_set: Set[str] = derived_ids,
        ) -> Tuple[str, ...]:
            raw_deps = deps_map.get(node_id, ())
            return tuple(d for d in raw_deps if d in node_set)

        try:
            _ = graph_utils.topological_sort(derived_ids, _get_derived_deps)
        except graph_utils.ScalimCyclicDependencyError as exc:
            cycles = exc.cycles or ()
            cycle = cycles[0] if cycles else ()
            chain = " -> ".join(str(x) for x in cycle) if cycle else "unknown"
            msg = "outputs.{}.aggregate.fields has cyclic dependency: {}".format(name, chain)
            raise ValueError(msg) from exc

    def _validate_aggregate_semantics(self, t: OutputTargetConfig, name: str, known_field_ids: Set[str]) -> None:
        agg = cast("OutputAggregateConfig", t.aggregate)  # pragma: allow-cast output target typed narrowing
        rank_field_ids, post_field_ids, allowed_agg_out_fields = self._validate_aggregate_group_and_metrics(t, name, known_field_ids, agg)
        agg_field_ids = set(agg.fields.keys())
        self._validate_rank_semantics(name, agg, rank_field_ids, allowed_agg_out_fields)
        self._validate_aggregate_post_semantics(name, agg, agg_field_ids, rank_field_ids, post_field_ids)
        self._validate_aggregate_derived_dag(name, agg, rank_field_ids, post_field_ids)

    def _validate_outputs_semantics(
        self,
        outputs: List[OutputTargetConfig],
        *,
        known_field_ids: Set[str],
    ) -> None:
        for idx, t in enumerate(outputs):
            name = str(t.name or "").strip()
            self._validate_output_binding_semantics(t, idx=int(idx))
            if t.aggregate is None:
                self._validate_detail_output_semantics(t, name, known_field_ids)
            else:
                self._validate_aggregate_semantics(t, name, known_field_ids)

    def _collect_required_field_ids_from_aggregate(self, agg: OutputAggregateConfig) -> List[str]:
        required: List[str] = []
        for cfg in agg.fields.values():
            if cfg.producer_key not in _AGG_FUNC_KEYS:
                continue
            agg_cfg = cast("Dict[str, Any]", cfg.config)  # pragma: allow-cast output aggregate config typed narrowing
            field_id = agg_cfg.get("field")
            if field_id:
                required.append(str(field_id))
            field_ids = agg_cfg.get("fields")
            if field_ids:
                required.extend([str(x) for x in field_ids])
        return required

    def _collect_required_field_ids_from_outputs(self, outputs: List[OutputTargetConfig]) -> Optional[List[str]]:
        required: List[str] = []
        for t in outputs:
            if t.aggregate is None:
                required.extend([str(x) for x in (t.fields or ())])
            else:
                agg = t.aggregate
                required.extend([str(x) for x in agg.group_by])
                required.extend(self._collect_required_field_ids_from_aggregate(agg))
            if t.requires:
                required.extend([str(x) for x in t.requires])
        return list(ordered_unique_str(required))


__all__ = ()
