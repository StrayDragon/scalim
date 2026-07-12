"""`effective outputs/resources` 触发判定的 `SSOT` 辅助函数.

本模块收敛“某个输出是否会写出 `header_fields_output_by=name` 的表头”这一类触发判定逻辑, 供以下边界复用以避免漂移:
- `workflow` `preflight`(`policy-aware`, 且不做 `demand YAML` `IO`)
- `demand` `runtime compile`(包含 `output composition`)

运行时需兼容 `Python 3.6`
"""

from typing import List, Optional, Tuple

from ....vendor.dataclassesx import replace
from ..book_resource_policy import ResourcesPolicy, resolve_write_defaults_config
from ..schema_dsl.constants import DEFAULT_OUTPUT_HEADER_BY, DEFAULT_OUTPUT_INCLUDE_HEADER
from ..schema_dsl.models import DemandConfig, OutputTargetConfig, OutputToConfig
from ..schema_dsl.output_enums import DEFAULT_BOOK_WRITE_HEADER_POLICY, DEFAULT_BOOK_WRITE_MODE
from .contracts import DemandRunOptions, OutputOverride, OutputsDefaultsOverride, ResourcesOverride


def apply_default_book_binding_to_outputs(
    outputs: Tuple[OutputTargetConfig, ...],
    *,
    default_book_id: str,
) -> Tuple[OutputTargetConfig, ...]:
    if not outputs:
        return outputs
    if not default_book_id:
        return outputs

    updated: List[OutputTargetConfig] = []
    for out_cfg in outputs:
        to_cfg = out_cfg.to
        if to_cfg is None:
            updated.append(replace(out_cfg, to=OutputToConfig(book=str(default_book_id))))
            continue

        file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
        book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
        if file_id or book_id:
            updated.append(out_cfg)
            continue

        updated.append(replace(out_cfg, to=replace(to_cfg, book=str(default_book_id))))

    return tuple(updated)


def effective_book_write_mode(
    config: DemandConfig,
    *,
    resources_override: Optional[ResourcesOverride],
    book_id: str,
    resources_policy: Optional[object] = None,
) -> str:
    _ = resources_override  # `IO` `overlay` 不再承载 `write` `policy`
    policy = resources_policy if isinstance(resources_policy, ResourcesPolicy) else None
    book_cfg = None
    if config.resources is not None:
        book_cfg = config.resources.books.get(str(book_id))
    if book_cfg is not None and book_cfg.write_defaults is not None:
        raw_text = str(book_cfg.write_defaults.mode or "").strip()
        if raw_text:
            return raw_text
    return str(resolve_write_defaults_config(book_id=str(book_id), resources_policy=policy).mode or DEFAULT_BOOK_WRITE_MODE)


def effective_book_header_policy(
    config: DemandConfig,
    *,
    resources_override: Optional[ResourcesOverride],
    book_id: str,
    resources_policy: Optional[object] = None,
) -> str:
    _ = resources_override  # `IO` `overlay` 不再承载 `write` `policy`
    policy = resources_policy if isinstance(resources_policy, ResourcesPolicy) else None
    book_cfg = None
    if config.resources is not None:
        book_cfg = config.resources.books.get(str(book_id))
    if book_cfg is not None and book_cfg.write_defaults is not None:
        raw_text = str(book_cfg.write_defaults.header_policy or "").strip()
        if raw_text:
            return raw_text
    return str(
        resolve_write_defaults_config(book_id=str(book_id), resources_policy=policy).header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY
    )


def output_target_requires_unique_effective_field_display_names(
    config: DemandConfig,
    output: OutputTargetConfig,
    *,
    resources_override: Optional[ResourcesOverride],
    resources_policy: Optional[object] = None,
) -> bool:
    to_cfg = output.to
    if to_cfg is None:
        return False

    write_cfg = output.write
    header_by = str(DEFAULT_OUTPUT_HEADER_BY)
    if write_cfg is not None and write_cfg.header_fields_output_by is not None:
        header_by = str(write_cfg.header_fields_output_by)
    if header_by != "name":
        return False

    file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
    if file_id:
        include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
        if write_cfg is not None and write_cfg.include_header is not None:
            include_header = bool(write_cfg.include_header)
        return bool(include_header)

    book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
    if not book_id:
        return False

    mode = effective_book_write_mode(config, resources_override=resources_override, book_id=str(book_id), resources_policy=resources_policy)
    header_policy = effective_book_header_policy(
        config, resources_override=resources_override, book_id=str(book_id), resources_policy=resources_policy
    )

    if str(mode).strip() == "append":
        return header_policy != "never"

    include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
    if write_cfg is not None and write_cfg.include_header is not None:
        include_header = bool(write_cfg.include_header)
    return bool(include_header)


def output_override_requires_unique_effective_field_display_names(
    config: DemandConfig,
    output: OutputOverride,
    *,
    default_book_id: Optional[str],
    resources_override: Optional[ResourcesOverride],
    resources_policy: Optional[object] = None,
) -> bool:
    to_cfg = output.to
    write_cfg = output.write

    header_by = str(DEFAULT_OUTPUT_HEADER_BY)
    if write_cfg is not None and write_cfg.header_fields_output_by is not None:
        header_by = str(write_cfg.header_fields_output_by)
    if header_by != "name":
        return False

    file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
    if file_id:
        include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
        if write_cfg is not None and write_cfg.include_header is not None:
            include_header = bool(write_cfg.include_header)
        return bool(include_header)

    book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
    if not book_id and default_book_id:
        book_id = str(default_book_id)
    if not book_id:
        return False

    mode = effective_book_write_mode(config, resources_override=resources_override, book_id=str(book_id), resources_policy=resources_policy)
    header_policy = effective_book_header_policy(
        config, resources_override=resources_override, book_id=str(book_id), resources_policy=resources_policy
    )

    if str(mode).strip() == "append":
        return header_policy != "never"

    include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
    if write_cfg is not None and write_cfg.include_header is not None:
        include_header = bool(write_cfg.include_header)
    return bool(include_header)


def outputs_require_unique_effective_field_display_names(
    config: DemandConfig,
    *,
    outputs: Tuple[OutputTargetConfig, ...],
    resources_override: Optional[ResourcesOverride],
    resources_policy: Optional[object] = None,
) -> bool:
    return any(
        output_target_requires_unique_effective_field_display_names(
            config, out_cfg, resources_override=resources_override, resources_policy=resources_policy
        )
        for out_cfg in outputs
    )


def output_overrides_require_unique_effective_field_display_names(
    config: DemandConfig,
    *,
    outputs: Tuple[OutputOverride, ...],
    default_book_id: Optional[str],
    resources_override: Optional[ResourcesOverride],
    resources_policy: Optional[object] = None,
) -> bool:
    return any(
        output_override_requires_unique_effective_field_display_names(
            config,
            out_override,
            default_book_id=default_book_id,
            resources_override=resources_override,
            resources_policy=resources_policy,
        )
        for out_override in outputs
    )


def options_require_unique_effective_field_display_names(
    config: DemandConfig,
    *,
    options: DemandRunOptions,
) -> bool:
    overrides = options.outputs.overrides
    outputs_override = None if overrides is None else overrides.outputs
    defaults = None if overrides is None else overrides.outputs_defaults
    resources_override = None if overrides is None else overrides.resources
    resources_policy = options.resources_policy

    default_book_id = None
    if defaults is not None and isinstance(defaults, OutputsDefaultsOverride):
        default_book_id = str(defaults.to.book or "").strip() or None

    if outputs_override is not None:
        return output_overrides_require_unique_effective_field_display_names(
            config,
            outputs=tuple(outputs_override),
            default_book_id=default_book_id,
            resources_override=resources_override,
            resources_policy=resources_policy,
        )

    outputs = tuple(config.outputs)
    if default_book_id is not None:
        outputs = apply_default_book_binding_to_outputs(outputs, default_book_id=str(default_book_id))
    return outputs_require_unique_effective_field_display_names(
        config,
        outputs=outputs,
        resources_override=resources_override,
        resources_policy=resources_policy,
    )
