import re
from dataclasses import replace
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from ...schema_dsl.constants import (
    DEFAULT_OUTPUT_ENCODING,
    DEFAULT_OUTPUT_HEADER_BY,
    DEFAULT_OUTPUT_INCLUDE_HEADER,
    DEFAULT_OUTPUT_STREAMING,
)
from ...schema_dsl.models import (
    DEMAND_KEYS,
    OUTPUT_AGGREGATE_KEYS,
    OUTPUT_AGGREGATE_METRIC_KEYS,
    OUTPUT_CONTAINER_KEYS,
    OUTPUT_TARGET_KEYS,
    OutputAggregateConfig,
    OutputAggregateMetricConfig,
    OutputContainerConfig,
    OutputTargetConfig,
)
from ..models import FieldDefIndex, RawDemand
from ..security import ComputeExpressionError, SecureComputeEngine, SecurityError, extract_compute_dependencies
from .utils import list_or_none, mapping_or_none, str_or_none

_OUTPUT_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_OUTPUT_CONTAINER_TYPES = ("workbook", "csv")
_OUTPUT_HEADER_BY_ENUM = ("field_id", "name")
_AGG_OP_ENUM = ("count", "sum", "min", "max", "count_true", "count_true_gte", "count_distinct")
_AGG_DISTINCT_ON_OVERFLOW_ENUM = ("error", "truncate")
_AGG_RANK_ORDER_ENUM = ("asc", "desc")


def _ordered_unique(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _non_empty_str(raw: object) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


class ParserOutputsMixin:
    def _validate_output_name(self, value: str, *, path: str) -> None:
        if not value:
            msg = "{} is required".format(path)
            raise ValueError(msg)
        if not _OUTPUT_NAME_PATTERN.match(value):
            msg = "{}={!r} is invalid; expected identifier like [a-zA-Z_][a-zA-Z0-9_]*".format(path, value)
            raise ValueError(msg)

    def _parse_outputs(  # noqa: C901, PLR0915
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
        engine = SecureComputeEngine()

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
                    known_field_ids=known_field_ids,
                    engine=engine,
                )
            )

        by_name: Dict[str, OutputTargetConfig] = {}
        for t in base_outputs:
            name = str(t.name or "").strip()
            self._validate_output_name(name, path="outputs.*.name")
            if name in by_name:
                msg = "Duplicate output name: {}".format(name)
                raise ValueError(msg)
            by_name[name] = t

        resolved: Dict[str, OutputTargetConfig] = {}
        visiting: Set[str] = set()

        def _resolve(name: str) -> OutputTargetConfig:
            existing = resolved.get(name)
            if existing is not None:
                return existing
            if name in visiting:
                msg = "outputs.*.from has a cycle at '{}'".format(name)
                raise ValueError(msg)
            visiting.add(name)
            current = by_name[name]

            container = current.container
            fields = current.fields

            from_name = str(current.from_ or "").strip() or None
            if from_name:
                base = by_name.get(from_name)
                if base is None:
                    msg = "outputs.{}.from points to unknown output: {}".format(name, from_name)
                    raise ValueError(msg)
                base_resolved = _resolve(from_name)
                if container is None:
                    container = base_resolved.container
                if current.aggregate is None and fields is None:
                    fields = base_resolved.fields
                    if fields is None:
                        msg = "outputs.{} inherits fields from '{}', but base output has no fields".format(name, from_name)
                        raise ValueError(msg)

            merged = replace(current, container=container, fields=fields)
            resolved[name] = merged
            visiting.remove(name)
            return merged

        resolved_outputs: List[OutputTargetConfig] = [_resolve(str(t.name)) for t in base_outputs]
        self._validate_outputs_semantics(resolved_outputs, known_field_ids=known_field_ids)

        required_field_ids = self._collect_required_field_ids_from_outputs(resolved_outputs)
        return tuple(resolved_outputs), required_field_ids

    def _parse_output_target(
        self,
        raw_target: Dict[str, Any],
        *,
        idx: int,
        outputs_key: str,
        known_field_ids: Set[str],
        engine: SecureComputeEngine,
    ) -> OutputTargetConfig:
        name = _non_empty_str(raw_target.get(OUTPUT_TARGET_KEYS["name"]))
        self._validate_output_name(name, path="{}.{}.name".format(outputs_key, idx))
        from_name = str_or_none(raw_target.get(OUTPUT_TARGET_KEYS["from_"]))
        from_name = _non_empty_str(from_name) or None
        if from_name:
            self._validate_output_name(from_name, path="{}.{}.from".format(outputs_key, idx))

        container_raw = mapping_or_none(raw_target.get(OUTPUT_TARGET_KEYS["container"]))
        container = (
            self._parse_output_container(container_raw, base_path="{}.{}.container".format(outputs_key, idx)) if container_raw else None
        )

        fields_raw = raw_target.get(OUTPUT_TARGET_KEYS["fields"])
        fields_list = list_or_none(fields_raw)
        if fields_raw is not None and fields_list is None:
            msg = "{}.{}.fields must be a list".format(outputs_key, idx)
            raise TypeError(msg)
        fields: Optional[Tuple[str, ...]] = None
        if fields_list is not None:
            normalized = [str(item or "").strip() for item in fields_list if str(item or "").strip()]
            fields = tuple(normalized) if normalized else ()

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
        aggregate = self._parse_output_aggregate(agg_raw, base_path="{}.{}.aggregate".format(outputs_key, idx)) if agg_raw else None

        return OutputTargetConfig(
            name=name,
            from_=from_name,
            container=container,
            fields=fields,
            where=where,
            aggregate=aggregate,
            requires=requires,
        )

    def _parse_output_container(self, raw: Dict[str, Any], *, base_path: str) -> OutputContainerConfig:
        type_raw = raw.get(OUTPUT_CONTAINER_KEYS["type"])
        typ = _non_empty_str(type_raw).lower()
        path = _non_empty_str(raw.get(OUTPUT_CONTAINER_KEYS["path"]))
        sheet = str_or_none(raw.get(OUTPUT_CONTAINER_KEYS["sheet"]))
        sheet = _non_empty_str(sheet) or None
        encoding = _non_empty_str(raw.get(OUTPUT_CONTAINER_KEYS["encoding"])) or DEFAULT_OUTPUT_ENCODING
        streaming = bool(raw.get(OUTPUT_CONTAINER_KEYS["streaming"], DEFAULT_OUTPUT_STREAMING))
        include_header = bool(raw.get(OUTPUT_CONTAINER_KEYS["include_header"], DEFAULT_OUTPUT_INCLUDE_HEADER))
        header_by = _non_empty_str(raw.get(OUTPUT_CONTAINER_KEYS["header_fields_output_by"])) or DEFAULT_OUTPUT_HEADER_BY
        allow_formulas = bool(raw.get(OUTPUT_CONTAINER_KEYS["allow_formulas"], False))
        write_lock = bool(raw.get(OUTPUT_CONTAINER_KEYS["write_lock"], False))

        if not typ:
            msg = "{}.type is required".format(base_path)
            raise ValueError(msg)
        if typ not in _OUTPUT_CONTAINER_TYPES:
            msg = "{}.type={!r} is invalid; expected one of: {}".format(base_path, typ, ", ".join(_OUTPUT_CONTAINER_TYPES))
            raise ValueError(msg)
        if not path:
            msg = "{}.path is required".format(base_path)
            raise ValueError(msg)
        if header_by not in _OUTPUT_HEADER_BY_ENUM:
            msg = "{}.header_fields_output_by={!r} is invalid; expected one of: {}".format(
                base_path, header_by, ", ".join(_OUTPUT_HEADER_BY_ENUM)
            )
            raise ValueError(msg)

        return OutputContainerConfig(
            type=typ,
            path=path,
            sheet=sheet,
            encoding=encoding,
            streaming=streaming,
            include_header=include_header,
            header_fields_output_by=header_by,
            allow_formulas=allow_formulas,
            write_lock=write_lock,
        )

    def _parse_output_aggregate(self, raw: Dict[str, Any], *, base_path: str) -> OutputAggregateConfig:
        group_by_raw = raw.get(OUTPUT_AGGREGATE_KEYS["group_by"])
        group_by_list = list_or_none(group_by_raw)
        if group_by_list is None:
            msg = "{}.group_by must be a list".format(base_path)
            raise TypeError(msg)
        group_by = tuple(str(item or "").strip() for item in group_by_list if str(item or "").strip())

        metrics_raw = mapping_or_none(raw.get(OUTPUT_AGGREGATE_KEYS["metrics"]))
        if metrics_raw is None:
            msg = "{}.metrics must be an object".format(base_path)
            raise TypeError(msg)
        metrics: Dict[str, OutputAggregateMetricConfig] = {}
        for out_field_id_raw, metric_raw in metrics_raw.items():
            out_field_id = str(out_field_id_raw or "").strip()
            metric_dict = mapping_or_none(metric_raw)
            if not out_field_id or metric_dict is None:
                continue
            metrics[out_field_id] = self._parse_output_aggregate_metric(
                metric_dict,
                base_path="{}.metrics.{}".format(base_path, out_field_id),
            )

        max_groups = int(raw.get(OUTPUT_AGGREGATE_KEYS["max_groups"], 0) or 0)
        if max_groups < 0:
            msg = "{}.max_groups must be >= 0".format(base_path)
            raise ValueError(msg)
        max_distinct = int(raw.get(OUTPUT_AGGREGATE_KEYS["max_distinct"], 0) or 0)
        if max_distinct < 0:
            msg = "{}.max_distinct must be >= 0".format(base_path)
            raise ValueError(msg)

        distinct_on_overflow = str(raw.get(OUTPUT_AGGREGATE_KEYS["distinct_on_overflow"], "error") or "error").lower()
        if distinct_on_overflow not in _AGG_DISTINCT_ON_OVERFLOW_ENUM:
            msg = "{}.distinct_on_overflow={!r} is invalid; expected one of: {}".format(
                base_path,
                distinct_on_overflow,
                ", ".join(_AGG_DISTINCT_ON_OVERFLOW_ENUM),
            )
            raise ValueError(msg)

        rank_order = str(raw.get(OUTPUT_AGGREGATE_KEYS["rank_order"], "desc") or "desc").lower()
        if rank_order not in _AGG_RANK_ORDER_ENUM:
            msg = "{}.rank_order={!r} is invalid; expected one of: {}".format(base_path, rank_order, ", ".join(_AGG_RANK_ORDER_ENUM))
            raise ValueError(msg)

        top_k = int(raw.get(OUTPUT_AGGREGATE_KEYS["top_k"], 0) or 0)
        if top_k < 0:
            msg = "{}.top_k must be >= 0".format(base_path)
            raise ValueError(msg)

        return OutputAggregateConfig(
            group_by=group_by,
            metrics=metrics,
            max_groups=max_groups,
            max_distinct=max_distinct,
            distinct_on_overflow=distinct_on_overflow,
            rank_by=str_or_none(raw.get(OUTPUT_AGGREGATE_KEYS["rank_by"])),
            rank_field_id=_non_empty_str(raw.get(OUTPUT_AGGREGATE_KEYS["rank_field_id"])) or "rank",
            rank_order=rank_order,
            top_k=top_k,
        )

    def _parse_output_aggregate_metric(
        self,
        raw: Dict[str, Any],
        *,
        base_path: str,
    ) -> OutputAggregateMetricConfig:
        op = _non_empty_str(raw.get(OUTPUT_AGGREGATE_METRIC_KEYS["op"])).lower()
        field_id = str_or_none(raw.get(OUTPUT_AGGREGATE_METRIC_KEYS["field_id"]))
        field_id = _non_empty_str(field_id) or None

        fields_raw = raw.get(OUTPUT_AGGREGATE_METRIC_KEYS["field_ids"])
        fields_list = list_or_none(fields_raw)
        if fields_raw is not None and fields_list is None:
            msg = "{}.fields must be a list".format(base_path)
            raise TypeError(msg)
        field_ids = None
        if fields_list is not None:
            normalized = [str(item or "").strip() for item in fields_list if str(item or "").strip()]
            field_ids = tuple(normalized) if normalized else ()

        threshold = raw.get(OUTPUT_AGGREGATE_METRIC_KEYS["threshold"])
        if not op:
            msg = "{}.op is required".format(base_path)
            raise ValueError(msg)
        if op not in _AGG_OP_ENUM:
            msg = "{}.op={!r} is invalid; expected one of: {}".format(base_path, op, ", ".join(_AGG_OP_ENUM))
            raise ValueError(msg)

        if op in ("sum", "min", "max", "count_true", "count_true_gte") and not field_id:
            msg = "{}.field is required for op={!r}".format(base_path, op)
            raise ValueError(msg)
        if op == "count_true_gte" and threshold is None:
            msg = "{}.threshold is required for op='count_true_gte'".format(base_path)
            raise ValueError(msg)
        if op == "count_distinct":
            if field_id and field_ids:
                msg = "{} does not allow both field and fields for op='count_distinct'".format(base_path)
                raise ValueError(msg)
            if not field_id and not field_ids:
                msg = "{} requires field or fields for op='count_distinct'".format(base_path)
                raise ValueError(msg)

        return OutputAggregateMetricConfig(
            op=op,
            field_id=field_id,
            field_ids=field_ids,
            threshold=threshold,
        )

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
        except (ComputeExpressionError, SecurityError) as exc:
            msg = "Invalid where expression at {}: {}".format(path, exc)
            raise ValueError(msg) from exc
        return deps

    def _validate_outputs_semantics(  # noqa: C901, PLR0912, PLR0915
        self,
        outputs: List[OutputTargetConfig],
        *,
        known_field_ids: Set[str],
    ) -> None:
        workbook_targets_by_path: Dict[str, List[str]] = {}

        for t in outputs:
            name = str(t.name or "").strip()
            container = t.container
            if container is None:
                msg = "outputs.{} missing required container (or inherit via from)".format(name)
                raise ValueError(msg)

            if not container.streaming:
                msg = "outputs.{}.container.streaming must be true (composed outputs only support streaming=true)".format(name)
                raise ValueError(msg)

            if container.type == "workbook":
                if container.path:
                    workbook_targets_by_path.setdefault(str(container.path), []).append(name)
            elif container.type == "csv":
                if container.sheet:
                    msg = "outputs.{}.container.sheet is only allowed for type=workbook".format(name)
                    raise ValueError(msg)
                if container.allow_formulas:
                    msg = "outputs.{}.container.allow_formulas is only allowed for type=workbook".format(name)
                    raise ValueError(msg)
                if container.write_lock:
                    msg = "outputs.{}.container.write_lock is only allowed for type=workbook".format(name)
                    raise ValueError(msg)

            if t.aggregate is None:
                if t.fields is None or not t.fields:
                    msg = "outputs.{} requires fields for detail output".format(name)
                    raise ValueError(msg)
                unknown_fields = [fid for fid in t.fields if fid not in known_field_ids]
                if unknown_fields:
                    msg = "outputs.{}.fields reference unknown fields: {}".format(name, ", ".join(sorted(set(unknown_fields))))
                    raise ValueError(msg)
            else:
                if t.fields is not None:
                    msg = "outputs.{} is an aggregate output and does not allow fields".format(name)
                    raise ValueError(msg)
                agg = t.aggregate
                if not agg.group_by:
                    msg = "outputs.{}.aggregate.group_by cannot be empty".format(name)
                    raise ValueError(msg)
                if not agg.metrics:
                    msg = "outputs.{}.aggregate.metrics cannot be empty".format(name)
                    raise ValueError(msg)
                out_field_ids = set(agg.metrics.keys())
                overlap = [fid for fid in agg.group_by if fid in out_field_ids]
                if overlap:
                    msg = "outputs.{}.aggregate.metrics ids conflict with group_by fields: {}".format(name, ", ".join(sorted(set(overlap))))
                    raise ValueError(msg)
                rank_field_id = str(agg.rank_field_id or "rank").strip()
                if rank_field_id and rank_field_id in agg.group_by:
                    msg = "outputs.{}.aggregate.rank_field_id conflicts with group_by field: {}".format(name, rank_field_id)
                    raise ValueError(msg)
                missing = [fid for fid in agg.group_by if fid not in known_field_ids]
                if missing:
                    msg = "outputs.{}.aggregate.group_by reference unknown fields: {}".format(name, ", ".join(sorted(set(missing))))
                    raise ValueError(msg)
                metric_required = self._collect_required_field_ids_from_aggregate(agg)
                missing = [fid for fid in metric_required if fid not in known_field_ids]
                if missing:
                    msg = "outputs.{}.aggregate.metrics reference unknown fields: {}".format(name, ", ".join(sorted(set(missing))))
                    raise ValueError(msg)

                # `rank_by` 必须引用 `group_by` 或指标 `out_field_id`
                rank_by = str(agg.rank_by or "").strip()
                if rank_by:
                    allowed = set(agg.group_by) | set(agg.metrics.keys())
                    if rank_by not in allowed:
                        msg = "outputs.{}.aggregate.rank_by={!r} must be one of group_by fields or metric ids: {}".format(
                            name,
                            rank_by,
                            ", ".join(sorted(allowed)),
                        )
                        raise ValueError(msg)
                if agg.rank_field_id and agg.rank_field_id in agg.metrics:
                    msg = "outputs.{}.aggregate.rank_field_id conflicts with metrics id: {}".format(name, agg.rank_field_id)
                    raise ValueError(msg)

        for path, names in workbook_targets_by_path.items():
            if len(names) <= 1:
                continue
            missing_sheet: List[str] = []
            for t in outputs:
                c = cast("OutputContainerConfig", t.container)
                if c.type != "workbook" or str(c.path) != str(path):
                    continue
                if not c.sheet:
                    missing_sheet.append(str(t.name))
            if missing_sheet:
                msg = "Multiple outputs share the same workbook path {!r}; each must set container.sheet. Missing: {}".format(
                    path,
                    ", ".join(sorted(missing_sheet)),
                )
                raise ValueError(msg)

    def _collect_required_field_ids_from_aggregate(self, agg: OutputAggregateConfig) -> List[str]:
        required: List[str] = []
        for m in agg.metrics.values():
            if m.field_id:
                required.append(str(m.field_id))
            if m.field_ids:
                required.extend([str(x) for x in m.field_ids])
        return required

    def _collect_required_field_ids_from_outputs(self, outputs: List[OutputTargetConfig]) -> Optional[List[str]]:
        required: List[str] = []
        for t in outputs:
            if t.aggregate is None:
                if t.fields:
                    required.extend([str(x) for x in t.fields])
            else:
                agg = t.aggregate
                required.extend([str(x) for x in agg.group_by])
                required.extend(self._collect_required_field_ids_from_aggregate(agg))
            if t.requires:
                required.extend([str(x) for x in t.requires])
        return _ordered_unique(required)
