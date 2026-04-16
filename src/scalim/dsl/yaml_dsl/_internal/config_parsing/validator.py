# pragma: allow-cast-file yaml validation boundary typed narrowing
# pragma: allow-c901-file plan: c60
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, cast

from ....._internal.type_narrowing import as_list, as_mapping
from .....vendor.compact.typing_extensionsx import TypeGuard
from .....vendor.dataclassesx import asdict, dataclass
from .....vendor.dataclassesx import field as dataclass_field
from ...init_var_nodes import ScalimInitVarNodeTypeError, ScalimInitVarNodeValueError, parse_init_var_mapping_node
from ...schema_dsl.models import (
    BOOK_KEYS,
    DEMAND_KEYS,
    FILE_KEYS,
    OUTPUT_TARGET_KEYS,
    RESOURCES_KEYS,
)
from .error_envelope import ScalimYamlValidationError
from .errors import ScalimConfigValidationError
from .imports import contains_import_syntax
from .models import FieldDefIndex, RawDemand, collect_field_defs, ensure_mapping
from .security import SecureComputeEngine, build_compute_engine
from .unknown_fields import find_unknown_fields
from .validators.fields import ValidatorFieldsMixin
from .validators.issues import (
    MAX_VALIDATION_ERROR_LINES,
    VALIDATION_SEVERITY_ERROR,
    VALIDATION_SEVERITY_WARNING,
    ValidationIssue,
    ValidationReport,
)
from .yaml_load import (
    YamlLocationIndex,
    load_yaml_mapping_text,
    lookup_yaml_location,
    normalize_yaml_diagnostic_path,
)

__all__ = ()


def _is_list(value: object) -> TypeGuard[List[object]]:
    return isinstance(value, list)


def _is_dict(value: object) -> TypeGuard[Dict[object, object]]:
    return isinstance(value, dict)


class ConfigValidator(ValidatorFieldsMixin):
    _schema_path: str
    _schema: Optional[Dict[str, Any]]
    _compute_engine: Optional[SecureComputeEngine]
    _step_allowed_fields_by_source: Dict[str, Set[str]]
    _max_validation_error_lines: int

    def __init__(
        self,
        schema_path: Optional[str] = None,
        max_validation_error_lines: Optional[int] = None,
    ) -> None:
        super().__init__()
        if schema_path is None:
            schema_path = str(Path(__file__).parent.parent.parent / "schema" / "demand.gen.json")
        self._schema_path = schema_path
        self._schema = None
        self._compute_engine = build_compute_engine()
        self._step_allowed_fields_by_source = {}
        self._max_validation_error_lines = int(
            max_validation_error_lines if max_validation_error_lines is not None else MAX_VALIDATION_ERROR_LINES
        )
        if self._max_validation_error_lines < 1:
            msg = "max_validation_error_lines must be >= 1"
            raise ValueError(msg)

    def _warn_and_strip_legacy_observability(self, config: Dict[str, Any], issues: List["ValidationIssue"]) -> Dict[str, Any]:
        if "observability" not in config:
            return config

        msg = (
            "Legacy YAML key 'observability' is no longer supported and will be ignored. "
            "Hint: configure observability via Python runtime entrypoints: "
            "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            "runtime=DemandRunRuntimeOptions(components=[Observer()/Hook()]), "
            "outputs=DemandRunOutputOptions(overrides=RunOverrides(viz_config=VizObserverConfig(...))), "
            "...))."
        )
        issues.append(ValidationIssue(severity=VALIDATION_SEVERITY_WARNING, message=msg, path="observability"))

        cleaned = dict(config)
        cleaned.pop("observability", None)
        return cleaned

    @staticmethod
    def _append_removed_runtime_policy_error(issues: List["ValidationIssue"], *, path: str, msg: str) -> None:
        issues.append(ValidationIssue(severity=VALIDATION_SEVERITY_ERROR, message=msg, path=path))

    def _error_and_strip_removed_demand_runtime_policy_fields(
        self,
        config: Dict[str, Any],
        issues: List["ValidationIssue"],
    ) -> Dict[str, Any]:
        cleaned = dict(config)
        cleaned = self._strip_removed_demand_runtime_policy_top_level(cleaned, issues)
        cleaned = self._strip_removed_demand_runtime_policy_main_source_retry(cleaned, issues)
        return self._strip_removed_demand_runtime_policy_sources_retry(cleaned, issues)

    def _error_and_strip_removed_output_extras_fields(
        self,
        config: Dict[str, Any],
        issues: List["ValidationIssue"],
    ) -> Dict[str, Any]:
        cleaned = dict(config)

        meta_msg = "YAML key 'meta' was moved out of YAML mainline (output extras boundary). "
        meta_msg = (
            meta_msg
            + "Hint: configure meta sheet via runtime entrypoints: "
            + "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            + "outputs=DemandRunOutputOptions(overrides=RunOverrides("
            + "output_extras=OutputExtrasOverride(meta=True))), ...))."
        )

        audit_msg = "YAML key 'audit' was moved out of YAML mainline (output extras boundary). "
        audit_msg = (
            audit_msg
            + "Hint: configure audit sheet via runtime entrypoints: "
            + "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            + "outputs=DemandRunOutputOptions(overrides=RunOverrides("
            + "output_extras=OutputExtrasOverride(audit=True))), ...))."
        )

        removed: Tuple[Tuple[str, str], ...] = (
            ("meta", meta_msg),
            ("audit", audit_msg),
        )

        for key, msg in removed:
            if key not in cleaned:
                continue
            ConfigValidator._append_removed_runtime_policy_error(issues, path=str(key), msg=msg)
            cleaned.pop(key, None)

        return cleaned

    def _error_and_strip_removed_output_write_workbook_fields(
        self,
        config: Dict[str, Any],
        issues: List["ValidationIssue"],
    ) -> Dict[str, Any]:
        outputs = as_list(config.get("outputs"), path="outputs")
        if not outputs:
            return config

        next_config: Optional[Dict[str, Any]] = None
        for idx, out_raw in enumerate(outputs):
            out = as_mapping(out_raw, path="outputs.{}".format(int(idx)))
            if out is None:
                continue

            write_raw = out.get("write")
            write_cfg = as_mapping(write_raw, path="outputs.{}.write".format(int(idx)))
            if write_cfg is None:
                continue

            removed: Tuple[str, ...] = (
                "mode",
                "align_by",
                "header_policy",
                "on_mismatch",
                "on_conflict",
            )

            removed_any = False
            next_write = dict(write_cfg)
            for key in removed:
                if key not in write_cfg:
                    continue
                removed_any = True
                ConfigValidator._append_removed_runtime_policy_error(
                    issues,
                    path="outputs.{}.write.{}".format(int(idx), str(key)),
                    msg=(
                        "YAML key 'outputs[*].write.{}' was moved out of output-local write config. "
                        "Hint: configure workbook write policy via resources.books.*.write_defaults.{}."
                    ).format(str(key), str(key)),
                )
                next_write.pop(key, None)

            if not removed_any:
                continue

            if next_config is None:
                next_config = dict(config)

            existing_outputs = as_list(next_config.get("outputs"), path="outputs") or []
            next_outputs = list(existing_outputs)
            next_out = dict(out)
            if next_write:
                next_out["write"] = next_write
            else:
                next_out.pop("write", None)
            next_outputs[int(idx)] = next_out
            next_config["outputs"] = next_outputs

        return config if next_config is None else next_config

    def _error_and_strip_removed_resources_write_lock_fields(  # noqa: C901, PLR0915
        self,
        config: Dict[str, Any],
        issues: List["ValidationIssue"],
    ) -> Dict[str, Any]:
        resources_raw: object = config.get(DEMAND_KEYS["resources"])
        if not _is_dict(resources_raw):
            return config

        resources = cast("Dict[str, Any]", resources_raw)  # pragma: allow-cast yaml mapping typed narrowing
        next_config: Optional[Dict[str, Any]] = None

        def _ensure_next_config() -> Dict[str, Any]:
            nonlocal next_config
            if next_config is None:
                next_config = dict(config)
            return next_config

        def _ensure_next_resources() -> Dict[str, Any]:
            c = _ensure_next_config()
            existing_resources = cast("Dict[str, Any]", c.get(DEMAND_KEYS["resources"]) or {})
            next_resources = dict(existing_resources)
            c[DEMAND_KEYS["resources"]] = next_resources
            return next_resources

        write_lock_hint = (
            "write_lock was removed (lockless versioned outputs). "
            "Migration: set resources.*.path to an output root directory and locate outputs via <root>/manifest/latest.json."
        )

        files_raw: object = resources.get(RESOURCES_KEYS["files"])
        if _is_dict(files_raw):
            files = cast("Dict[str, Any]", files_raw)  # pragma: allow-cast yaml mapping typed narrowing
            for raw_file_id, raw_file_cfg in files.items():
                file_id = str(raw_file_id or "").strip()
                if not file_id or not _is_dict(raw_file_cfg):
                    continue
                file_cfg = cast("Dict[str, Any]", raw_file_cfg)  # pragma: allow-cast yaml mapping typed narrowing
                if "write_lock" not in file_cfg:
                    continue
                self._add_error(
                    issues,
                    "resources.files.{}.write_lock was removed; {}".format(file_id, write_lock_hint),
                    path="resources.files.{}.write_lock".format(file_id),
                )
                next_resources = _ensure_next_resources()
                next_files = dict(cast("Dict[str, Any]", next_resources.get(RESOURCES_KEYS["files"]) or files))
                next_file_cfg = dict(file_cfg)
                next_file_cfg.pop("write_lock", None)
                next_files[str(raw_file_id)] = next_file_cfg
                next_resources[RESOURCES_KEYS["files"]] = next_files

        books_raw: object = resources.get(RESOURCES_KEYS["books"])
        if _is_dict(books_raw):
            books = cast("Dict[str, Any]", books_raw)  # pragma: allow-cast yaml mapping typed narrowing
            for raw_book_id, raw_book_cfg in books.items():
                book_id = str(raw_book_id or "").strip()
                if not book_id or not _is_dict(raw_book_cfg):
                    continue
                book_cfg = cast("Dict[str, Any]", raw_book_cfg)  # pragma: allow-cast yaml mapping typed narrowing

                if "write_lock" in book_cfg:
                    self._add_error(
                        issues,
                        "resources.books.{}.write_lock was removed; {}".format(book_id, write_lock_hint),
                        path="resources.books.{}.write_lock".format(book_id),
                    )
                    next_resources = _ensure_next_resources()
                    next_books = dict(cast("Dict[str, Any]", next_resources.get(RESOURCES_KEYS["books"]) or books))
                    next_book_cfg = dict(book_cfg)
                    next_book_cfg.pop("write_lock", None)
                    next_books[str(raw_book_id)] = next_book_cfg
                    next_resources[RESOURCES_KEYS["books"]] = next_books

                export_raw = book_cfg.get(BOOK_KEYS["export_xlsx"])
                if not _is_dict(export_raw):
                    continue
                export_cfg = cast("Dict[str, Any]", export_raw)  # pragma: allow-cast yaml mapping typed narrowing
                if "write_lock" not in export_cfg:
                    continue
                self._add_error(
                    issues,
                    "resources.books.{}.export_xlsx.write_lock was removed; {}".format(book_id, write_lock_hint),
                    path="resources.books.{}.export_xlsx.write_lock".format(book_id),
                )
                next_resources = _ensure_next_resources()
                next_books = dict(cast("Dict[str, Any]", next_resources.get(RESOURCES_KEYS["books"]) or books))
                next_book_cfg = dict(cast("Dict[str, Any]", next_books.get(str(raw_book_id)) or book_cfg))
                next_export_cfg = dict(export_cfg)
                next_export_cfg.pop("write_lock", None)
                next_book_cfg[BOOK_KEYS["export_xlsx"]] = next_export_cfg
                next_books[str(raw_book_id)] = next_book_cfg
                next_resources[RESOURCES_KEYS["books"]] = next_books

        return config if next_config is None else next_config

    @staticmethod
    def _strip_removed_demand_runtime_policy_top_level(
        cleaned: Dict[str, Any],
        issues: List["ValidationIssue"],
    ) -> Dict[str, Any]:
        guardrails_msg = "YAML key 'guardrails' was moved out of YAML mainline (runtime policy boundary). "
        guardrails_msg = (
            guardrails_msg
            + "Hint: configure guardrails via runtime entrypoints: "
            + "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            + "runtime=DemandRunRuntimeOptions(guardrails=GuardrailsPolicy(...)), ...))."
        )

        batch_size_msg = "YAML key 'batch_size' was moved out of YAML mainline (runtime policy boundary). "
        batch_size_msg = (
            batch_size_msg
            + "Hint: configure batch size via runtime entrypoints: "
            + "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            + "runtime=DemandRunRuntimeOptions(batch_size=<int|None>), ...))."
        )

        demand_failure_policy_msg = "YAML key 'failure_policy' was moved out of demand YAML mainline (runtime policy boundary). "
        demand_failure_policy_msg = (
            demand_failure_policy_msg
            + "Hint: configure demand output failure policy via runtime entrypoints: "
            + "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            + "runtime=DemandRunRuntimeOptions(demand_failure_policy='all_fail'|'primary_only'), ...))."
        )

        retry_msg = "YAML key 'retry' was moved out of YAML mainline (runtime policy boundary). "
        retry_msg = (
            retry_msg
            + "Hint: configure loader retry via runtime entrypoints: "
            + "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            + "runtime=DemandRunRuntimeOptions(loader_retry=LoaderRetryPoliciesSpec(...)), ...))."
        )

        validate_unique_field_names_msg = (
            "YAML key 'validate_unique_field_names' was moved out of demand YAML mainline (runtime policy boundary). "
        )
        validate_unique_field_names_msg = (
            validate_unique_field_names_msg
            + "Hint: configure demand diagnostics via runtime entrypoints: "
            + "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            + "runtime=DemandRunRuntimeOptions(demand_diagnostics=DemandDiagnosticsPolicy("
            + "validate_unique_field_names=False)), ...))."
        )

        include_full_error_message_msg = (
            "YAML key 'include_full_error_message' was moved out of demand YAML mainline (runtime policy boundary). "
        )
        include_full_error_message_msg = (
            include_full_error_message_msg
            + "Hint: configure demand diagnostics via runtime entrypoints: "
            + "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            + "runtime=DemandRunRuntimeOptions(demand_diagnostics=DemandDiagnosticsPolicy("
            + "include_full_error_message=True)), ...))."
        )

        removed: Tuple[Tuple[str, str], ...] = (
            (
                "guardrails",
                guardrails_msg,
            ),
            (
                "batch_size",
                batch_size_msg,
            ),
            (
                "failure_policy",
                demand_failure_policy_msg,
            ),
            (
                "retry",
                retry_msg,
            ),
            (
                "validate_unique_field_names",
                validate_unique_field_names_msg,
            ),
            (
                "include_full_error_message",
                include_full_error_message_msg,
            ),
        )

        for key, msg in removed:
            if key not in cleaned:
                continue
            ConfigValidator._append_removed_runtime_policy_error(issues, path=str(key), msg=msg)
            cleaned.pop(key, None)

        return cleaned

    @staticmethod
    def _strip_removed_demand_runtime_policy_main_source_retry(
        cleaned: Dict[str, Any],
        issues: List["ValidationIssue"],
    ) -> Dict[str, Any]:
        main_source = as_mapping(cleaned.get("main_source"), path="main_source")
        if main_source is None or "retry" not in main_source:
            return cleaned

        ConfigValidator._append_removed_runtime_policy_error(
            issues,
            path="main_source.retry",
            msg=(
                "YAML key 'main_source.retry' was moved out of YAML mainline (runtime policy boundary). "
                "Hint: configure loader retry via runtime entrypoints: "
                "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
                "runtime=DemandRunRuntimeOptions(loader_retry=LoaderRetryPoliciesSpec(by_loader={...})), ...))."
            ),
        )
        next_main: Dict[str, Any] = dict(main_source)
        next_main.pop("retry", None)
        cleaned["main_source"] = next_main
        return cleaned

    @staticmethod
    def _strip_removed_demand_runtime_policy_sources_retry(
        cleaned: Dict[str, Any],
        issues: List["ValidationIssue"],
    ) -> Dict[str, Any]:
        sources = as_mapping(cleaned.get("sources"), path="sources")
        if sources is None:
            return cleaned

        next_sources: Optional[Dict[str, Any]] = None
        for source_id, source_cfg_raw in sources.items():
            source_cfg = as_mapping(source_cfg_raw, path="sources.{}".format(str(source_id)))
            if source_cfg is None or "retry" not in source_cfg:
                continue

            if next_sources is None:
                next_sources = dict(sources)

            ConfigValidator._append_removed_runtime_policy_error(
                issues,
                path="sources.{}.retry".format(str(source_id)),
                msg=(
                    "YAML key 'sources.*.retry' was moved out of YAML mainline (runtime policy boundary). "
                    "Hint: configure loader retry via runtime entrypoints: "
                    "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
                    "runtime=DemandRunRuntimeOptions(loader_retry=LoaderRetryPoliciesSpec(by_loader={...})), ...))."
                ),
            )
            next_cfg: Dict[str, Any] = dict(source_cfg)
            next_cfg.pop("retry", None)
            next_sources[str(source_id)] = next_cfg

        if next_sources is not None:
            cleaned["sources"] = next_sources
        return cleaned

    def validate(self, config: Dict[str, Any]) -> None:
        report = self.validate_report(config, strict_unknown_fields=True)
        issues = report.errors()
        if not issues:
            return

        errors: List[str] = []
        for issue in issues[: self._max_validation_error_lines]:
            if issue.path:
                errors.append("{}: {}".format(issue.path, issue.message))
            else:
                errors.append(issue.message)

        msg = "Configuration validation failed with {} error(s)".format(len(issues))
        if len(issues) > self._max_validation_error_lines:
            msg = "{} (showing first {} errors)".format(msg, self._max_validation_error_lines)
        raise ScalimConfigValidationError(msg, errors=errors, issues=report.issues)

    def validate_report(
        self,
        config: Dict[str, Any],
        *,
        strict_unknown_fields: bool = False,
    ) -> ValidationReport:
        errors: List[ValidationIssue] = []
        config = self._warn_and_strip_legacy_observability(config, errors)
        config = self._error_and_strip_removed_demand_runtime_policy_fields(config, errors)
        config = self._error_and_strip_removed_output_extras_fields(config, errors)
        config = self._error_and_strip_removed_output_write_workbook_fields(config, errors)
        config = self._error_and_strip_removed_resources_write_lock_fields(config, errors)
        raw = RawDemand.from_raw(config)

        self._validate_required_fields(raw.data, errors)
        self._validate_legacy_fields(raw.data, errors)

        sources_info = self._validate_sources(raw.data, errors)
        main_source_id = self._validate_main_source(raw.data, errors)
        self._step_allowed_fields_by_source = self._collect_step_allowed_fields(raw.data, main_source_id)
        relation_paths = self._validate_relations(raw.data, errors, sources_info, main_source_id)
        self._validate_fields(raw, errors, sources_info, main_source_id, relation_paths)
        self._validate_outputs_shape(raw.data, errors)
        self._validate_outputs_fields_object_refs(raw, errors, main_source_id=main_source_id)
        self._validate_outputs_detail_requires_fields_or_from(raw.data, errors)
        self._validate_removed_output_container(raw.data, errors)
        self._validate_resource_output_paths(raw.data, errors)

        self._validate_unknown_fields(raw.data, errors, strict=strict_unknown_fields)

        return ValidationReport(issues=errors)

    def _validate_outputs_shape(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:
        outputs_key = DEMAND_KEYS["outputs"]
        outputs_raw = config.get(outputs_key)
        if outputs_raw is None:
            return
        if not isinstance(outputs_raw, list):
            self._add_error(errors, "'{}' must be a list".format(outputs_key), path=str(outputs_key))
            return

        outputs_list = cast("List[Any]", outputs_raw)  # pragma: allow-cast yaml list typed narrowing
        for idx, item in enumerate(outputs_list):
            if isinstance(item, dict):
                continue
            self._add_error(errors, "outputs.{} must be a dictionary".format(int(idx)), path="outputs.{}".format(int(idx)))

    def _validate_outputs_detail_requires_fields_or_from(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:
        outputs_raw: object = config.get(DEMAND_KEYS["outputs"])
        if not _is_list(outputs_raw):
            return
        outputs = outputs_raw

        fields_key = OUTPUT_TARGET_KEYS["fields"]
        from_key = OUTPUT_TARGET_KEYS["from_"]
        aggregate_key = OUTPUT_TARGET_KEYS["aggregate"]
        name_key = OUTPUT_TARGET_KEYS["name"]

        for idx, item in enumerate(outputs):
            if not isinstance(item, dict):
                continue
            out_dict = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing

            # `$import` 会在编译期展开; 允许仅声明 `$import` 的形态绕过结构性约束.
            if "$import" in out_dict and set(out_dict.keys()) == {"$import"}:
                continue

            if out_dict.get(aggregate_key) is not None:
                continue

            fields_raw = out_dict.get(fields_key)
            from_raw = out_dict.get(from_key)
            has_fields = isinstance(fields_raw, list) and bool(cast("List[Any]", fields_raw))
            has_from = isinstance(from_raw, str) and bool(from_raw.strip())
            if has_fields or has_from:
                continue

            name_raw = out_dict.get(name_key)
            output_name = name_raw.strip() if isinstance(name_raw, str) else ""
            label = output_name or str(int(idx))
            msg = "outputs.{} requires fields for detail output (or set from to inherit fields)".format(label)
            self._add_error(errors, msg, path="outputs.{}.{}".format(int(idx), fields_key))

    def _validate_removed_output_container(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:
        outputs_raw = config.get(DEMAND_KEYS["outputs"])
        if not _is_list(outputs_raw):
            return
        for idx, item in enumerate(outputs_raw):
            if not isinstance(item, dict):
                continue
            out_dict = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing
            if "container" not in out_dict:
                continue
            msg = (
                "outputs.{}.container was removed; migrate CSV outputs to resources.files + outputs[*].to.file + outputs[*].write, "
                "and .xlsx outputs to resources.books + outputs[*].to.book / outputs[*].to.sheet + outputs[*].write"
            ).format(int(idx))
            self._add_error(errors, msg, path="outputs.{}.container".format(int(idx)))

    def _build_aggregate_field_index(self, aggregate: Dict[str, Any]) -> Tuple[Dict[int, str], List[Tuple[str, Dict[str, Any]]]]:
        fields_raw: object = aggregate.get("fields")
        if not _is_dict(fields_raw):
            return {}, []
        fields_dict = fields_raw

        alias_index: Dict[int, str] = {}
        field_defs: List[Tuple[str, Dict[str, Any]]] = []
        for out_field_id_raw, field_raw in fields_dict.items():
            out_field_id = str(out_field_id_raw or "").strip()
            if not out_field_id:
                continue
            if not isinstance(field_raw, dict):
                continue
            field_dict = cast("Dict[str, Any]", field_raw)  # pragma: allow-cast yaml mapping typed narrowing
            alias_index[id(field_dict)] = out_field_id
            field_defs.append((out_field_id, field_dict))
        return alias_index, field_defs

    def _outputs_fields_object_item_error(
        self,
        field_def_index: FieldDefIndex,
        item: object,
        *,
        agg_field_index: Optional[Tuple[Dict[int, str], List[Tuple[str, Dict[str, Any]]]]] = None,
    ) -> Optional[str]:
        if not isinstance(item, dict):
            return "must be field_id string, YAML alias(object), or YAML alias(list)"

        typed = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing
        if agg_field_index is not None:
            alias_index, _ = agg_field_index
            if alias_index.get(id(typed)) is not None:
                return None

        direct = field_def_index.alias_index.get(typed)
        if direct is not None:
            return None

        matches: List[str] = []
        if agg_field_index is not None:
            _, field_defs = agg_field_index
            matches.extend([out_field_id for out_field_id, data in field_defs if data == typed])
        matches.extend([fd.field_id for fd in field_def_index.field_defs if fd.data == typed])

        if not matches:
            return "cannot resolve object to a unique field_id; prefer string field_id"

        unique = sorted(set(matches))
        if len(unique) > 1:
            return "ambiguous object entry; matches multiple id values: {}. Use string field_id to disambiguate.".format(", ".join(unique))
        return None

    def _validate_outputs_fields_list_object_refs(
        self,
        fields_list: List[Any],
        errors: List[ValidationIssue],
        *,
        base_path: str,
        field_def_index: FieldDefIndex,
        agg_field_index: Optional[Tuple[Dict[int, str], List[Tuple[str, Dict[str, Any]]]]] = None,
    ) -> None:
        def _walk(item: object, *, path: str) -> List[Tuple[str, object]]:
            if _is_list(item):
                out: List[Tuple[str, object]] = []
                for idx, sub in enumerate(item):
                    out.extend(_walk(sub, path="{}.{}".format(path, idx)))
                return out
            return [(path, item)]

        for field_idx, item in enumerate(fields_list):
            root_path = "{}.{}".format(base_path, field_idx)
            for leaf_path, leaf in _walk(item, path=root_path):
                if isinstance(leaf, str):
                    continue
                msg = self._outputs_fields_object_item_error(field_def_index, leaf, agg_field_index=agg_field_index)
                if msg:
                    self._add_error(errors, msg, path=leaf_path)

    def _validate_outputs_fields_object_refs(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        *,
        main_source_id: str,
    ) -> None:
        # 注意: `jsonschema` 校验是可选项; `schema-only` 校验不应阻断 `YAML` `alias` 写法.
        # 这里做语义校验,确保 `outputs[*].fields` 的 `object` 条目可解析为唯一 `field_id`.
        field_def_index = collect_field_defs(raw, main_source_id=main_source_id)

        outputs_key = DEMAND_KEYS["outputs"]
        outputs_raw = raw.data.get(outputs_key)
        if not isinstance(outputs_raw, list):
            return
        outputs_list = cast("List[Any]", outputs_raw)  # pragma: allow-cast yaml list typed narrowing

        fields_key = OUTPUT_TARGET_KEYS["fields"]

        for output_idx, output_raw in enumerate(outputs_list):
            if not isinstance(output_raw, dict):
                continue
            output_dict = cast("Dict[str, Any]", output_raw)  # pragma: allow-cast yaml mapping typed narrowing
            fields_raw = output_dict.get(fields_key)
            if not isinstance(fields_raw, list):
                continue
            fields_list = cast("List[Any]", fields_raw)  # pragma: allow-cast yaml list typed narrowing

            agg_field_index = None
            agg_raw = output_dict.get("aggregate")
            if isinstance(agg_raw, dict):
                agg_field_index = self._build_aggregate_field_index(
                    cast("Dict[str, Any]", agg_raw)  # pragma: allow-cast yaml mapping typed narrowing
                )

            base_path = "{}.{}.{}".format(outputs_key, output_idx, fields_key)
            self._validate_outputs_fields_list_object_refs(
                fields_list,
                errors,
                base_path=base_path,
                field_def_index=field_def_index,
                agg_field_index=agg_field_index,
            )

    def _load_schema(self) -> Dict[str, Any]:
        if self._schema is None:
            with Path(self._schema_path).open("r", encoding="utf-8") as f:
                self._schema = json.load(f)
        if self._schema is None:  # pragma: no cover  # pragma: allow-no-cover invariant: schema loaded or raised above
            msg = "Schema failed to load"
            raise RuntimeError(msg)
        return self._schema

    def _validate_unknown_fields(self, config: Dict[str, Any], issues: List[ValidationIssue], *, strict: bool) -> None:
        try:
            schema = self._load_schema()
        except Exception:  # noqa: BLE001
            return

        severity = VALIDATION_SEVERITY_ERROR if strict else VALIDATION_SEVERITY_WARNING
        for unknown in find_unknown_fields(config, schema):
            issues.append(
                ValidationIssue(
                    severity=severity,
                    message=unknown.message,
                    path=unknown.path,
                    suggestions=unknown.suggestions,
                )
            )

    def _validate_resource_output_paths(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:  # noqa: C901, PLR0912, PLR0915
        resources_raw = config.get(DEMAND_KEYS["resources"])
        if not isinstance(resources_raw, dict):
            return

        files_raw = cast("Any", resources_raw).get(RESOURCES_KEYS["files"])
        if isinstance(files_raw, dict):
            for raw_file_id, raw_file_cfg in cast("Dict[Any, Any]", files_raw).items():  # pragma: allow-cast yaml mapping typed narrowing
                file_id = str(raw_file_id or "").strip()
                if not file_id or not isinstance(raw_file_cfg, dict):
                    continue
                # 语义升级: `path` 应为 `output root` 目录 (旧语义常见为 `./out/detail.csv`)
                file_cfg = cast("Dict[str, Any]", raw_file_cfg)  # pragma: allow-cast yaml mapping typed narrowing
                kind_raw = file_cfg.get(FILE_KEYS["kind"])
                kind = str(kind_raw or "").strip()
                path_value = file_cfg.get(FILE_KEYS["path"])
                if kind == "csv_file" and (path_value is None or (isinstance(path_value, str) and not path_value.strip())):
                    msg = "resources.files.{}.path is required for kind=csv_file".format(file_id)
                    self._add_error(errors, msg, path="resources.files.{}".format(file_id))
                if isinstance(path_value, str) and Path(path_value).suffix.lower() == ".csv":
                    msg = (
                        "resources.files.{}.path now expects an output root directory, not a file path. "
                        "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
                    ).format(file_id)
                    self._add_error(errors, msg, path="resources.files.{}.path".format(file_id))
                path_raw = file_cfg.get(FILE_KEYS["path"])
                if not isinstance(path_raw, dict):
                    continue
                try:
                    _ = parse_init_var_mapping_node(
                        cast("Dict[str, Any]", path_raw),  # pragma: allow-cast yaml mapping typed narrowing
                        path="resources.files.{}.path".format(file_id),
                    )
                except (ScalimInitVarNodeValueError, ScalimInitVarNodeTypeError) as exc:
                    self._add_error(errors, exc.reason, path=exc.path)

        books_raw = cast("Any", resources_raw).get(RESOURCES_KEYS["books"])
        if not isinstance(books_raw, dict):
            return
        for raw_book_id, raw_book_cfg in cast("Dict[Any, Any]", books_raw).items():  # pragma: allow-cast yaml mapping typed narrowing
            book_id = str(raw_book_id or "").strip()
            if not book_id or not isinstance(raw_book_cfg, dict):
                continue
            book_cfg = cast("Dict[str, Any]", raw_book_cfg)  # pragma: allow-cast yaml mapping typed narrowing
            kind_raw = book_cfg.get(BOOK_KEYS["kind"])
            kind = str(kind_raw or "").strip()
            for suffix in ("path",):
                path_raw = book_cfg.get(suffix)
                if kind == "xlsx_file" and isinstance(path_raw, str) and Path(path_raw).suffix.lower() == ".xlsx":
                    msg = (
                        "resources.books.{}.path now expects an output root directory, not a file path. "
                        "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
                    ).format(book_id)
                    self._add_error(errors, msg, path="resources.books.{}.path".format(book_id))
                if not isinstance(path_raw, dict):
                    continue
                try:
                    _ = parse_init_var_mapping_node(
                        cast("Dict[str, Any]", path_raw),
                        path="resources.books.{}.{}".format(book_id, suffix),
                    )
                except (ScalimInitVarNodeValueError, ScalimInitVarNodeTypeError) as exc:
                    self._add_error(errors, exc.reason, path=exc.path)
            export_raw = book_cfg.get(BOOK_KEYS["export_xlsx"])
            if not isinstance(export_raw, dict):
                continue
            export_path_raw = cast("Dict[str, Any]", export_raw).get("path")
            if kind == "xlsx_memory" and isinstance(export_path_raw, str) and Path(export_path_raw).suffix.lower() == ".xlsx":
                msg = (
                    "resources.books.{}.export_xlsx.path now expects an output root directory, not a file path. "
                    "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
                ).format(book_id)
                self._add_error(errors, msg, path="resources.books.{}.export_xlsx.path".format(book_id))
            if not isinstance(export_path_raw, dict):
                continue
            try:
                _ = parse_init_var_mapping_node(
                    cast("Dict[str, Any]", export_path_raw),
                    path="resources.books.{}.export_xlsx.path".format(book_id),
                )
            except (ScalimInitVarNodeValueError, ScalimInitVarNodeTypeError) as exc:
                self._add_error(errors, exc.reason, path=exc.path)


@dataclass(frozen=True)
class YamlValidationIssue:
    path: str
    message: str
    suggestions: List[str] = dataclass_field(default_factory=list)
    line: Optional[int] = None
    column: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.line is None:
            payload.pop("line", None)
        if self.column is None:
            payload.pop("column", None)
        return payload


@dataclass(frozen=True)
class YamlValidationResult:
    ok: bool
    errors: List[YamlValidationIssue] = dataclass_field(default_factory=list)
    warnings: List[YamlValidationIssue] = dataclass_field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


def _issues_to_rows(issues: Iterable[ValidationIssue]) -> List[YamlValidationIssue]:
    rows: List[YamlValidationIssue] = []
    for issue in issues:
        rows.append(
            YamlValidationIssue(
                path=normalize_yaml_diagnostic_path(str(issue.path or "")),
                message=str(issue.message),
                suggestions=list(issue.suggestions),
            )
        )
    return rows


def attach_locations(
    issues: List[YamlValidationIssue],
    locations: YamlLocationIndex,
    *,
    default: Optional[Tuple[int, int]] = (1, 1),
) -> List[YamlValidationIssue]:
    if not issues:
        return issues
    output: List[YamlValidationIssue] = []
    for issue in issues:
        if issue.line is not None:
            output.append(issue)
            continue
        loc = lookup_yaml_location(issue.path, locations)
        if loc is None:
            if default is None:
                output.append(issue)
                continue
            line, column = default
        else:
            line, column = loc
        output.append(
            YamlValidationIssue(
                path=issue.path,
                message=issue.message,
                suggestions=issue.suggestions,
                line=line,
                column=column,
            )
        )
    return output


def validate_yaml_text(
    yaml_text: str,
    strict_unknown_fields: bool = False,  # noqa: FBT001, FBT002
    schema_path: Optional[str] = None,
) -> YamlValidationResult:
    """使用 `Scalim` 内置校验器对 `YAML DSL` 文本进行校验.

    此函数会做语义校验(`ConfigValidator`),并基于 `YAML` 语法树(`AST`)位置索引尽力补充行/列定位信息.
    """
    try:
        yaml_data, locations, _lines = load_yaml_mapping_text(
            yaml_text,
            source_path="(memory)",
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        errors: List[YamlValidationIssue] = []
        for envelope in exc.errors:
            loc = envelope.loc
            errors.append(
                YamlValidationIssue(
                    path=str(envelope.path or "(root)"),
                    message=str(envelope.message),
                    suggestions=list(envelope.suggestions),
                    line=loc.line if loc is not None else None,
                    column=loc.column if loc is not None else None,
                )
            )
        warnings: List[YamlValidationIssue] = []
        for envelope in exc.warnings:
            loc = envelope.loc
            warnings.append(
                YamlValidationIssue(
                    path=str(envelope.path or "(root)"),
                    message=str(envelope.message),
                    suggestions=list(envelope.suggestions),
                    line=loc.line if loc is not None else None,
                    column=loc.column if loc is not None else None,
                )
            )
        return YamlValidationResult(ok=False, errors=errors, warnings=warnings)

    if contains_import_syntax(yaml_data):
        msg = "imports/$import is only supported for file path entrypoints; use scalim-cli yaml-dsl validate <file.yaml>"
        return YamlValidationResult(
            ok=False,
            errors=[YamlValidationIssue(path="(root)", message=msg, line=1, column=1)],
            warnings=[],
        )

    validator = ConfigValidator(schema_path=schema_path)
    config_data = ensure_mapping(yaml_data)
    report = validator.validate_report(
        config_data,
        strict_unknown_fields=bool(strict_unknown_fields),
    )

    errors = _issues_to_rows(report.errors())
    warnings = _issues_to_rows(report.warnings())

    errors = attach_locations(errors, locations)
    warnings = attach_locations(warnings, locations)

    ok = not errors
    return YamlValidationResult(ok=bool(ok), errors=errors, warnings=warnings)


def validate_yaml_text_json(
    yaml_text: str,
    strict_unknown_fields: bool = False,  # noqa: FBT001, FBT002
    schema_path: Optional[str] = None,
) -> str:
    """返回与 `YAML DSL` 编辑器的“精确校验器”兼容的 `JSON` 载荷."""
    result = validate_yaml_text(
        yaml_text,
        strict_unknown_fields,
        schema_path,
    )
    return json.dumps(result.as_dict(), ensure_ascii=False)
