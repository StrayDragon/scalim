from typing import Any, Dict, List, Optional, Set, Tuple

from ..parsers.utils import list_or_none, mapping_or_none
from .constants import F
from .issues import ValidationIssue
from .sources import ValidatorSourcesMixin

_F = F


class ValidatorRelationsMixin(ValidatorSourcesMixin):
    def _validate_relations(
        self,
        config: Dict[str, Any],
        errors: List[ValidationIssue],
        sources_info: Dict[str, Dict[str, bool]],
        main_source_id: str,
    ) -> Dict[str, List[Tuple[str, str, bool]]]:
        relations_raw = mapping_or_none(config.get(_F.RELATIONS, {}))
        if relations_raw is None:
            if config.get(_F.RELATIONS) is not None:
                self._add_error(errors, "'{}' must be a dictionary".format(_F.RELATIONS), path=_F.RELATIONS)
            return {}

        sources_set: Set[str] = set(sources_info.keys())
        if main_source_id:
            sources_set.add(main_source_id)

        derived_field_ids = self._collect_declared_field_names(config.get(_F.FIELDS))

        relation_paths: Dict[str, List[Tuple[str, str, bool]]] = {}
        for rel_id_raw, rel_data_raw in relations_raw.items():
            rel_id = str(rel_id_raw)
            rel_dict = mapping_or_none(rel_data_raw)
            if rel_dict is None:
                self._add_error(errors, "Relation '{}' must be a dictionary".format(rel_id), path="relations.{}".format(rel_id))
                continue

            steps_raw = rel_dict.get(_F.STEPS)
            steps = self._validate_steps(
                steps_raw,
                sources_set,
                errors,
                "relations.{}".format(rel_id),
                main_source_id=main_source_id,
                derived_field_ids=derived_field_ids,
            )
            relation_paths[rel_id] = steps

        return relation_paths

    def _validate_steps(  # noqa: C901, PLR0912
        self,
        steps_raw: Any,
        sources_set: Set[str],
        errors: List[ValidationIssue],
        context: str,
        *,
        main_source_id: str = "",
        derived_field_ids: Optional[Set[str]] = None,
    ) -> List[Tuple[str, str, bool]]:
        steps_list = list_or_none(steps_raw)
        if steps_list is None:
            self._add_error(errors, "{} steps must be a list".format(context), path="{}.steps".format(context))
            return []
        if not steps_list:
            self._add_error(errors, "{} steps must not be empty".format(context), path="{}.steps".format(context))
            return []

        steps: List[Tuple[str, str, bool]] = []
        prev_to_source: Optional[str] = None

        for idx, step_raw in enumerate(steps_list):
            step_path = "{}.steps.{}".format(context, idx)
            step_dict = mapping_or_none(step_raw)
            if step_dict is None:
                self._add_error(errors, "{} steps[{}] must be a dictionary".format(context, idx), path=step_path)
                continue

            if _F.FROM not in step_dict or _F.TO not in step_dict:
                self._add_error(errors, "{} steps[{}] missing 'from' or 'to'".format(context, idx), path=step_path)
                continue

            from_info = self._parse_source_field_group(step_dict.get(_F.FROM))
            to_info = self._parse_source_field_group(step_dict.get(_F.TO))
            if from_info is None or to_info is None:
                self._add_error(errors, "{} steps[{}] from/to must be source.field or list".format(context, idx), path=step_path)
                continue

            from_source, from_fields = from_info
            to_source, to_fields = to_info

            if from_source not in sources_set:
                self._add_error(
                    errors,
                    "{} steps[{}] references unknown source '{}'".format(context, idx, from_source),
                    path=step_path,
                )
            if to_source not in sources_set:
                self._add_error(
                    errors,
                    "{} steps[{}] references unknown source '{}'".format(context, idx, to_source),
                    path=step_path,
                )

            if self._step_allowed_fields_by_source:
                derived_allowed = (
                    derived_field_ids if derived_field_ids is not None and main_source_id and from_source == main_source_id else None
                )
                self._validate_step_field_names(
                    from_source,
                    from_fields,
                    sources_set,
                    errors,
                    "{} steps[{}]".format(context, idx),
                    "{}.{}".format(step_path, _F.FROM),
                    derived_allowed_fields=derived_allowed,
                )
                self._validate_step_field_names(
                    to_source,
                    to_fields,
                    sources_set,
                    errors,
                    "{} steps[{}]".format(context, idx),
                    "{}.{}".format(step_path, _F.TO),
                )

            if len(from_fields) != len(to_fields):
                self._add_error(errors, "{} steps[{}] from/to field length mismatch".format(context, idx), path=step_path)

            if prev_to_source is not None and from_source != prev_to_source:
                self._add_error(
                    errors,
                    "{} steps[{}] breaks chain: expected from source '{}'".format(context, idx, prev_to_source),
                    path=step_path,
                )

            prev_to_source = to_source
            has_to_bind = False

            lookup_raw = step_dict.get(_F.LOOKUP_CAST)
            if lookup_raw is not None:
                self._validate_lookup_cast(lookup_raw, errors, "{} steps[{}]".format(context, idx), step_path)

            to_bind_raw = step_dict.get(_F.TO_BIND)
            if to_bind_raw is not None:
                self._add_error(
                    errors,
                    (
                        "Legacy YAML syntax is not supported: '{}'. "
                        "Move binding into the target source's `params` template using `$keys` / `$rows` directives."
                        "\nExample:\n"
                        "  sources:\n"
                        "    <to_source_id>:\n"
                        "      params:\n"
                        "        ids:\n"
                        "          $keys: {{as: set}}"
                    ).format("{}.{}".format(step_path, _F.TO_BIND)),
                    path="{}.{}".format(step_path, _F.TO_BIND),
                )

            steps.append((from_source, to_source, has_to_bind))

        return steps

    def _validate_step_field_names(
        self,
        source_id: str,
        fields: List[str],
        sources_set: Set[str],
        errors: List[ValidationIssue],
        context: str,
        path: str,
        derived_allowed_fields: Optional[Set[str]] = None,
    ) -> None:
        if source_id not in sources_set:
            return
        allowed = self._step_allowed_fields_by_source.get(source_id)
        if allowed is None:
            return
        for field_name in fields:
            if field_name in allowed:
                continue
            if derived_allowed_fields is not None and field_name in derived_allowed_fields:
                continue
            base_msg = (
                "{} references unknown field '{}.{}'; "
                "relation steps must use field_id (YAML key), not loader data_key. "
                "Define it under main_source.fields or sources.{}.fields (or use sources.{}.key for key fields)"
            ).format(
                context,
                source_id,
                field_name,
                source_id,
                source_id,
            )

            suggestions = sorted(self._step_field_ids_by_source_data_key.get(source_id, {}).get(field_name, set()))
            if not suggestions:
                self._add_error(errors, base_msg, path=path)
                continue

            step_key = path.rsplit(".", 1)[-1] if path else "from"
            suggested = suggestions[0]
            fix_snippet = "  {}: {}.{}".format(step_key, source_id, suggested)
            msg = "{}\nLikely field_id: {}\nFix snippet:\n{}".format(base_msg, ", ".join(suggestions), fix_snippet)
            self._add_error(errors, msg, path=path)

    def _validate_relation_paths_for_field(
        self,
        field_id: str,
        source_id: str,
        main_source_id: str,
        relation_paths: Dict[str, List[Tuple[str, str, bool]]],
        errors: List[ValidationIssue],
        field_path: str,
    ) -> None:
        path_count = self._count_paths(main_source_id, source_id, relation_paths)
        if path_count == 0:
            self._add_error(
                errors,
                "Field '{}' has no relation path from main_source to '{}'; specify relation".format(field_id, source_id),
                path="{}.{}".format(field_path, _F.RELATION),
            )
        elif path_count > 1:
            self._add_error(
                errors,
                "Field '{}' has ambiguous relation paths to '{}'; specify relation".format(field_id, source_id),
                path="{}.{}".format(field_path, _F.RELATION),
            )

    def _validate_steps_binding_requirements(
        self,
        steps: List[Tuple[str, str, bool]],
        sources_info: Dict[str, Dict[str, bool]],
        errors: List[ValidationIssue],
        context: str,
    ) -> None:
        _ = (steps, sources_info, errors, context)
        # 绑定通过目标 `source` 的 `params` 模板(`$keys`/`$rows`)表达,不再使用 `legacy` `to_bind`/`bind`.

    def _validate_relation_path(
        self,
        field_id: str,
        source_id: str,
        main_source_id: str,
        steps: List[Tuple[str, str, bool]],
        errors: List[ValidationIssue],
        field_path: str,
    ) -> None:
        if not steps:
            self._add_error(
                errors,
                "Field '{}' relation steps is empty".format(field_id),
                path="{}.{}".format(field_path, _F.RELATION),
            )
            return
        start_source, end_source = steps[0][0], steps[-1][1]
        if main_source_id and start_source != main_source_id:
            self._add_error(
                errors,
                "Field '{}' relation must start from main_source '{}'".format(field_id, main_source_id),
                path="{}.{}".format(field_path, _F.RELATION),
            )
        if end_source != source_id:
            self._add_error(
                errors,
                "Field '{}' relation must end at source '{}'".format(field_id, source_id),
                path="{}.{}".format(field_path, _F.RELATION),
            )

    def _parse_source_field_expr(self, expr: Any) -> Optional[Tuple[str, str]]:
        if not isinstance(expr, str):
            return None
        if "." not in expr:
            return None
        parts = expr.split(".", 1)
        expected_parts = 2
        if len(parts) != expected_parts:
            return None
        source_id, field_name = parts[0].strip(), parts[1].strip()
        if not source_id or not field_name:
            return None
        return source_id, field_name

    def _parse_source_field_group(self, value: Any) -> Optional[Tuple[str, List[str]]]:
        if isinstance(value, str):
            parsed = self._parse_source_field_expr(value)
            if parsed is None:
                return None
            return parsed[0], [parsed[1]]

        source_id: Optional[str] = None
        fields: List[str] = []
        values = list_or_none(value)
        if values:
            for item in values:
                parsed = self._parse_source_field_expr(item)
                if parsed is None:
                    source_id = None
                    fields = []
                    break
                if source_id is None:
                    source_id = parsed[0]
                elif source_id != parsed[0]:
                    source_id = None
                    fields = []
                    break
                fields.append(parsed[1])

        if source_id is None:
            return None
        return source_id, fields

    def _count_paths(self, start: str, target: str, relation_paths: Dict[str, List[Tuple[str, str, bool]]]) -> int:
        if not start or not target:
            return 0
        adjacency: Dict[str, List[Tuple[str, str]]] = {}
        for rel_id, steps in relation_paths.items():
            for idx, (from_source, to_source, _has_to_bind) in enumerate(steps):
                adjacency.setdefault(from_source, []).append((to_source, "{}:{}".format(rel_id, idx)))

        max_paths = 2
        paths_found = 0
        queue: List[Tuple[str, Set[str]]] = [(start, {start})]

        while queue and paths_found < max_paths:
            current, visited = queue.pop(0)
            if current == target:
                paths_found += 1
                continue
            for next_source, _edge_id in adjacency.get(current, []):
                if next_source in visited:
                    continue
                next_visited = set(visited)
                next_visited.add(next_source)
                queue.append((next_source, next_visited))

        return paths_found


__all__ = []
