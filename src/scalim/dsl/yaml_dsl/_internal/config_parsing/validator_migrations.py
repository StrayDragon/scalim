# pragma: allow-cast-file yaml validation boundary typed narrowing
# pragma: allow-c901-file plan: c60
"""`ConfigValidator` 的遗留字段迁移与剥离逻辑.

在校验前扫描原始 YAML 配置字典,对已移除或已弃用的键执行自动剥离,
并生成对应的 `ValidationIssue` 条目供校验报告使用.
"""

from typing import TYPE_CHECKING, Any, cast

from ....._internal.type_narrowing import as_list, as_mapping
from ...schema_dsl.models import (
    BOOK_KEYS,
    DEMAND_KEYS,
    FILE_KEYS,
    RESOURCES_KEYS,
)

if TYPE_CHECKING:
    from typing import TypeGuard
from .validators.base import ValidatorMixinBase
from .validators.issues import (
    VALIDATION_SEVERITY_ERROR,
    ValidationIssue,
)

__all__ = ()


def _is_dict(value: Any) -> "TypeGuard[dict[Any, Any]]":
    return isinstance(value, dict)


class ValidatorMigrationsMixin(ValidatorMixinBase):
    """为 `ConfigValidator` 提供遗留字段迁移方法的 `Mixin`."""

    def _error_and_strip_legacy_observability(self, config: dict[str, Any], issues: list["ValidationIssue"]) -> dict[str, Any]:
        if "observability" not in config:
            return config

        msg = (
            "Legacy YAML key 'observability' is no longer supported. "
            "Hint: configure observability via Python runtime entrypoints: "
            "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
            "runtime=DemandRunRuntimeOptions(components=[Observer()/Hook()]), "
            "outputs=DemandRunOutputOptions(overrides=RunOverrides(viz_config=VizObserverConfig(...))), "
            "...))."
        )
        issues.append(ValidationIssue(severity=VALIDATION_SEVERITY_ERROR, message=msg, path="observability"))

        cleaned = dict(config)
        cleaned.pop("observability", None)
        return cleaned

    @staticmethod
    def _append_removed_runtime_policy_error(issues: list["ValidationIssue"], *, path: str, msg: str) -> None:
        issues.append(ValidationIssue(severity=VALIDATION_SEVERITY_ERROR, message=msg, path=path))

    def _error_and_strip_removed_demand_runtime_policy_fields(
        self,
        config: dict[str, Any],
        issues: list["ValidationIssue"],
    ) -> dict[str, Any]:
        cleaned = dict(config)
        cleaned = self._strip_removed_demand_runtime_policy_top_level(cleaned, issues)
        cleaned = self._strip_removed_demand_runtime_policy_main_source_retry(cleaned, issues)
        return self._strip_removed_source_runtime_policy_keys(cleaned, issues)

    def _error_and_strip_removed_output_extras_fields(
        self,
        config: dict[str, Any],
        issues: list["ValidationIssue"],
    ) -> dict[str, Any]:
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

        removed: tuple[tuple[str, str], ...] = (
            ("meta", meta_msg),
            ("audit", audit_msg),
        )

        for key, msg in removed:
            if key not in cleaned:
                continue
            ValidatorMigrationsMixin._append_removed_runtime_policy_error(issues, path=str(key), msg=msg)
            cleaned.pop(key, None)

        return cleaned

    def _error_and_strip_removed_output_write_workbook_fields(
        self,
        config: dict[str, Any],
        issues: list["ValidationIssue"],
    ) -> dict[str, Any]:
        outputs = as_list(config.get("outputs"), path="outputs")
        if not outputs:
            return config

        next_config: dict[str, Any] | None = None
        for idx, out_raw in enumerate(outputs):
            out = as_mapping(out_raw, path=f"outputs.{int(idx)}")
            if out is None:
                continue

            write_raw = out.get("write")
            write_cfg = as_mapping(write_raw, path=f"outputs.{int(idx)}.write")
            if write_cfg is None:
                continue

            removed: tuple[str, ...] = (
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
                ValidatorMigrationsMixin._append_removed_runtime_policy_error(
                    issues,
                    path=f"outputs.{int(idx)}.write.{key!s}",
                    msg=(
                        f"YAML key 'outputs[*].write.{key!s}' was moved out of output-local write config. "
                        "Hint: configure workbook write policy via DemandRunOptions.resources_policy "
                        f"/ WorkflowRunOptions.resources_policy (BookWritePolicy.{key!s})."
                    ),
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

    def _error_and_strip_removed_resources_write_lock_fields(  # noqa: C901, PLR0912, PLR0915
        self,
        config: dict[str, Any],
        issues: list["ValidationIssue"],
    ) -> dict[str, Any]:
        resources_raw: Any = config.get(DEMAND_KEYS["resources"])
        if not _is_dict(resources_raw):
            return config

        resources = cast("dict[str, Any]", resources_raw)  # pragma: allow-cast yaml mapping typed narrowing
        next_config: dict[str, Any] | None = None

        def _ensure_next_config() -> dict[str, Any]:
            nonlocal next_config
            if next_config is None:
                next_config = dict(config)
            return next_config

        def _ensure_next_resources() -> dict[str, Any]:
            c = _ensure_next_config()
            existing_resources = cast("dict[str, Any]", c.get(DEMAND_KEYS["resources"]) or {})
            next_resources = dict(existing_resources)
            c[DEMAND_KEYS["resources"]] = next_resources
            return next_resources

        write_lock_hint = (
            "write_lock was removed (lockless versioned outputs). "
            "Migration: set resources.files.*.csv_file.path / resources.books.*.*.path to an output root directory "
            "and locate outputs via <root>/manifest/latest.json."
        )

        files_raw: Any = resources.get(RESOURCES_KEYS["files"])
        if _is_dict(files_raw):
            files = cast("dict[str, Any]", files_raw)  # pragma: allow-cast yaml mapping typed narrowing
            for raw_file_id, raw_file_cfg in files.items():
                file_id = str(raw_file_id or "").strip()
                if not file_id or not _is_dict(raw_file_cfg):
                    continue
                file_cfg = cast("dict[str, Any]", raw_file_cfg)  # pragma: allow-cast yaml mapping typed narrowing
                next_file_cfg: dict[str, Any] | None = None

                if "write_lock" in file_cfg:
                    self._add_error(
                        issues,
                        f"resources.files.{file_id}.write_lock was removed; {write_lock_hint}",
                        path=f"resources.files.{file_id}.write_lock",
                    )
                    next_file_cfg = dict(file_cfg)
                    next_file_cfg.pop("write_lock", None)

                csv_raw = file_cfg.get(FILE_KEYS["csv_file"])
                if _is_dict(csv_raw):
                    csv_cfg = cast("dict[str, Any]", csv_raw)  # pragma: allow-cast yaml mapping typed narrowing
                    if "write_lock" in csv_cfg:
                        self._add_error(
                            issues,
                            f"resources.files.{file_id}.csv_file.write_lock was removed; {write_lock_hint}",
                            path=f"resources.files.{file_id}.csv_file.write_lock",
                        )
                        if next_file_cfg is None:
                            next_file_cfg = dict(file_cfg)
                        next_csv = dict(csv_cfg)
                        next_csv.pop("write_lock", None)
                        next_file_cfg[FILE_KEYS["csv_file"]] = next_csv

                if next_file_cfg is not None:
                    next_resources = _ensure_next_resources()
                    next_files = dict(cast("dict[str, Any]", next_resources.get(RESOURCES_KEYS["files"]) or files))
                    next_files[str(raw_file_id)] = next_file_cfg
                    next_resources[RESOURCES_KEYS["files"]] = next_files

        books_raw: Any = resources.get(RESOURCES_KEYS["books"])
        if _is_dict(books_raw):
            books = cast("dict[str, Any]", books_raw)  # pragma: allow-cast yaml mapping typed narrowing
            for raw_book_id, raw_book_cfg in books.items():
                book_id = str(raw_book_id or "").strip()
                if not book_id or not _is_dict(raw_book_cfg):
                    continue
                book_cfg = cast("dict[str, Any]", raw_book_cfg)  # pragma: allow-cast yaml mapping typed narrowing
                next_book_cfg: dict[str, Any] | None = None

                if "write_lock" in book_cfg:
                    self._add_error(
                        issues,
                        f"resources.books.{book_id}.write_lock was removed; {write_lock_hint}",
                        path=f"resources.books.{book_id}.write_lock",
                    )
                    next_book_cfg = dict(book_cfg)
                    next_book_cfg.pop("write_lock", None)

                export_raw = book_cfg.get("export_xlsx")
                if _is_dict(export_raw):
                    export_cfg = cast("dict[str, Any]", export_raw)  # pragma: allow-cast yaml mapping typed narrowing
                    if "write_lock" in export_cfg:
                        self._add_error(
                            issues,
                            f"resources.books.{book_id}.export_xlsx.write_lock was removed; {write_lock_hint}",
                            path=f"resources.books.{book_id}.export_xlsx.write_lock",
                        )
                        if next_book_cfg is None:
                            next_book_cfg = dict(book_cfg)
                        next_export_cfg = dict(export_cfg)
                        next_export_cfg.pop("write_lock", None)
                        next_book_cfg["export_xlsx"] = next_export_cfg

                xlsx_file_raw = book_cfg.get("xlsx_file")
                if _is_dict(xlsx_file_raw):
                    xlsx_file_cfg = cast("dict[str, Any]", xlsx_file_raw)  # pragma: allow-cast yaml mapping typed narrowing
                    if "write_lock" in xlsx_file_cfg:
                        self._add_error(
                            issues,
                            f"resources.books.{book_id}.xlsx_file.write_lock was removed; {write_lock_hint}",
                            path=f"resources.books.{book_id}.xlsx_file.write_lock",
                        )
                        if next_book_cfg is None:
                            next_book_cfg = dict(book_cfg)
                        next_xlsx_file = dict(xlsx_file_cfg)
                        next_xlsx_file.pop("write_lock", None)
                        next_book_cfg["xlsx_file"] = next_xlsx_file

                xlsx_memory_raw = book_cfg.get("xlsx_memory")
                if _is_dict(xlsx_memory_raw):
                    xlsx_memory_cfg = cast("dict[str, Any]", xlsx_memory_raw)  # pragma: allow-cast yaml mapping typed narrowing
                    if "write_lock" in xlsx_memory_cfg:
                        self._add_error(
                            issues,
                            f"resources.books.{book_id}.xlsx_memory.write_lock was removed; {write_lock_hint}",
                            path=f"resources.books.{book_id}.xlsx_memory.write_lock",
                        )
                        if next_book_cfg is None:
                            next_book_cfg = dict(book_cfg)
                        next_xlsx_memory = dict(xlsx_memory_cfg)
                        next_xlsx_memory.pop("write_lock", None)
                        next_book_cfg["xlsx_memory"] = next_xlsx_memory

                    export_mem_raw = xlsx_memory_cfg.get("export_xlsx")
                    if _is_dict(export_mem_raw):
                        export_mem_cfg = cast("dict[str, Any]", export_mem_raw)  # pragma: allow-cast yaml mapping typed narrowing
                        if "write_lock" in export_mem_cfg:
                            self._add_error(
                                issues,
                                f"resources.books.{book_id}.xlsx_memory.export_xlsx.write_lock was removed; {write_lock_hint}",
                                path=f"resources.books.{book_id}.xlsx_memory.export_xlsx.write_lock",
                            )
                            if next_book_cfg is None:
                                next_book_cfg = dict(book_cfg)
                            next_xlsx_memory = dict(cast("dict[str, Any]", next_book_cfg.get("xlsx_memory") or xlsx_memory_cfg))
                            next_export_mem = dict(export_mem_cfg)
                            next_export_mem.pop("write_lock", None)
                            next_xlsx_memory["export_xlsx"] = next_export_mem
                            next_book_cfg["xlsx_memory"] = next_xlsx_memory

                if next_book_cfg is not None:
                    next_resources = _ensure_next_resources()
                    next_books = dict(cast("dict[str, Any]", next_resources.get(RESOURCES_KEYS["books"]) or books))
                    next_books[str(raw_book_id)] = next_book_cfg
                    next_resources[RESOURCES_KEYS["books"]] = next_books

        return config if next_config is None else next_config

    def _error_and_strip_removed_resources_write_budget_fields(  # noqa: C901, PLR0915
        self,
        config: dict[str, Any],
        issues: list["ValidationIssue"],
    ) -> dict[str, Any]:
        resources_raw: Any = config.get(DEMAND_KEYS["resources"])
        if not _is_dict(resources_raw):
            return config

        resources = cast("dict[str, Any]", resources_raw)  # pragma: allow-cast yaml mapping typed narrowing
        books_raw = resources.get(RESOURCES_KEYS["books"])
        if not _is_dict(books_raw):
            return config
        books = cast("dict[str, Any]", books_raw)  # pragma: allow-cast yaml mapping typed narrowing

        write_hint = (
            "write_defaults was removed from YAML authoring (Python ResourcesPolicy SSOT). "
            "Migration: configure BookWritePolicy via DemandRunOptions.resources_policy "
            "or WorkflowRunOptions.resources_policy; omit for builtin defaults."
        )
        budget_hint = (
            "budget was removed. Delete this field; book cell/sheet budget is no longer "
            "supported — rely on host resource limits for memory risk."
        )

        next_config: dict[str, Any] | None = None

        def _ensure_next_resources() -> dict[str, Any]:
            nonlocal next_config
            if next_config is None:
                next_config = dict(config)
                next_config[DEMAND_KEYS["resources"]] = dict(resources)
            return cast("dict[str, Any]", next_config[DEMAND_KEYS["resources"]])  # pragma: allow-cast

        for raw_book_id, book_raw in books.items():
            book_cfg = as_mapping(book_raw, path=f"resources.books.{raw_book_id}")
            if book_cfg is None:
                continue
            next_book_cfg: dict[str, Any] | None = None

            if "write_defaults" in book_cfg:
                ValidatorMigrationsMixin._append_removed_runtime_policy_error(
                    issues,
                    msg=f"resources.books.{raw_book_id}.write_defaults was removed; {write_hint}",
                    path=f"resources.books.{raw_book_id}.write_defaults",
                )
                next_book_cfg = dict(book_cfg)
                next_book_cfg.pop("write_defaults", None)

            xlsx_memory_raw = book_cfg.get("xlsx_memory")
            xlsx_memory_cfg = as_mapping(
                xlsx_memory_raw,
                path=f"resources.books.{raw_book_id}.xlsx_memory",
            )
            if xlsx_memory_cfg is not None and "budget" in xlsx_memory_cfg:
                ValidatorMigrationsMixin._append_removed_runtime_policy_error(
                    issues,
                    msg=f"resources.books.{raw_book_id}.xlsx_memory.budget was removed; {budget_hint}",
                    path=f"resources.books.{raw_book_id}.xlsx_memory.budget",
                )
                if next_book_cfg is None:
                    next_book_cfg = dict(book_cfg)
                next_xlsx_memory = dict(xlsx_memory_cfg)
                next_xlsx_memory.pop("budget", None)
                next_book_cfg["xlsx_memory"] = next_xlsx_memory

            xlsx_raw = book_cfg.get(BOOK_KEYS["xlsx"])
            xlsx_cfg = as_mapping(xlsx_raw, path=f"resources.books.{raw_book_id}.xlsx")
            if xlsx_cfg is not None and "budget" in xlsx_cfg:
                ValidatorMigrationsMixin._append_removed_runtime_policy_error(
                    issues,
                    msg=f"resources.books.{raw_book_id}.xlsx.budget was removed; {budget_hint}",
                    path=f"resources.books.{raw_book_id}.xlsx.budget",
                )
                if next_book_cfg is None:
                    next_book_cfg = dict(book_cfg)
                next_xlsx = dict(xlsx_cfg)
                next_xlsx.pop("budget", None)
                next_book_cfg[BOOK_KEYS["xlsx"]] = next_xlsx
            if xlsx_cfg is not None and "write_defaults" in xlsx_cfg:
                ValidatorMigrationsMixin._append_removed_runtime_policy_error(
                    issues,
                    msg=f"resources.books.{raw_book_id}.xlsx.write_defaults was removed; {write_hint}",
                    path=f"resources.books.{raw_book_id}.xlsx.write_defaults",
                )
                if next_book_cfg is None:
                    next_book_cfg = dict(book_cfg)
                next_xlsx = dict(cast("dict[str, Any]", next_book_cfg.get(BOOK_KEYS["xlsx"]) or xlsx_cfg))
                next_xlsx.pop("write_defaults", None)
                next_book_cfg[BOOK_KEYS["xlsx"]] = next_xlsx

            if next_book_cfg is not None:
                next_resources = _ensure_next_resources()
                next_books = dict(cast("dict[str, Any]", next_resources.get(RESOURCES_KEYS["books"]) or books))
                next_books[str(raw_book_id)] = next_book_cfg
                next_resources[RESOURCES_KEYS["books"]] = next_books

        return config if next_config is None else next_config

    @staticmethod
    def _strip_removed_demand_runtime_policy_top_level(
        cleaned: dict[str, Any],
        issues: list["ValidationIssue"],
    ) -> dict[str, Any]:
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

        output_write_layout_msg = (
            "YAML key 'output_write_layout' is not part of YAML authoring (runtime policy boundary). "
            "Hint: configure via Python DemandRunOptions.runtime="
            "DemandRunRuntimeOptions(output_write_layout=OutputWriteLayout.ROW_STREAM|COLUMN_BUFFERED|COLUMN_CHUNKED). "
            "See upgrade 2026-08-11-output-write-layout."
        )
        excel_column_residency_msg = (
            "YAML key 'excel_column_residency' is not part of YAML authoring (runtime policy boundary). "
            "Hint: prefer DemandRunRuntimeOptions(output_write_layout=OutputWriteLayout.COLUMN_CHUNKED) "
            "(migration window: excel_column_residency=ExcelColumnResidency.CHUNKED). "
            "See docs/doc/getting-started/excel-column-residency.md."
        )

        removed: tuple[tuple[str, str], ...] = (
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
            (
                "output_write_layout",
                output_write_layout_msg,
            ),
            (
                "excel_column_residency",
                excel_column_residency_msg,
            ),
        )

        for key, msg in removed:
            if key not in cleaned:
                continue
            ValidatorMigrationsMixin._append_removed_runtime_policy_error(issues, path=str(key), msg=msg)
            cleaned.pop(key, None)

        return cleaned

    @staticmethod
    def _strip_removed_demand_runtime_policy_main_source_retry(
        cleaned: dict[str, Any],
        issues: list["ValidationIssue"],
    ) -> dict[str, Any]:
        main_source = as_mapping(cleaned.get("main_source"), path="main_source")
        if main_source is None or "retry" not in main_source:
            return cleaned

        ValidatorMigrationsMixin._append_removed_runtime_policy_error(
            issues,
            path="main_source.retry",
            msg=(
                "YAML key 'main_source.retry' was moved out of YAML mainline (runtime policy boundary). "
                "Hint: configure loader retry via runtime entrypoints: "
                "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
                "runtime=DemandRunRuntimeOptions(loader_retry=LoaderRetryPoliciesSpec(by_loader={...})), ...))."
            ),
        )
        next_main: dict[str, Any] = dict(main_source)
        next_main.pop("retry", None)
        cleaned["main_source"] = next_main
        return cleaned

    @staticmethod
    def _strip_removed_source_runtime_policy_keys(
        cleaned: dict[str, Any],
        issues: list["ValidationIssue"],
    ) -> dict[str, Any]:
        sources = as_mapping(cleaned.get("sources"), path="sources")
        if sources is None:
            return cleaned

        next_sources: dict[str, Any] | None = None
        for source_id, source_cfg_raw in sources.items():
            source_cfg = as_mapping(source_cfg_raw, path=f"sources.{source_id!s}")
            if source_cfg is None:
                continue

            remove_keys: list[tuple[str, str]] = []
            if "retry" in source_cfg:
                remove_keys.append(
                    (
                        "retry",
                        (
                            "YAML key 'sources.*.retry' was moved out of YAML mainline (runtime policy boundary). "
                            "Hint: configure loader retry via runtime entrypoints: "
                            "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
                            "runtime=DemandRunRuntimeOptions(loader_retry=LoaderRetryPoliciesSpec(by_loader={...})), ...))."
                        ),
                    )
                )
            if "lookup_chunk_size" in source_cfg:
                remove_keys.append(
                    (
                        "lookup_chunk_size",
                        (
                            f"sources.{source_id!s}.lookup_chunk_size was moved out of YAML authoring. "
                            "Configure LookupChunking via DemandRunOptions.runtime "
                            "(DemandRunRuntimeOptions.lookup_chunking={...: LookupChunking.sized(...)}); "
                            "see upgrade notes."
                        ),
                    )
                )
            if not remove_keys:
                continue

            if next_sources is None:
                next_sources = dict(sources)

            next_cfg: dict[str, Any] = dict(source_cfg)
            for key, msg in remove_keys:
                ValidatorMigrationsMixin._append_removed_runtime_policy_error(
                    issues,
                    path=f"sources.{source_id!s}.{key}",
                    msg=msg,
                )
                next_cfg.pop(key, None)
            next_sources[str(source_id)] = next_cfg

        if next_sources is not None:
            cleaned["sources"] = next_sources
        return cleaned
