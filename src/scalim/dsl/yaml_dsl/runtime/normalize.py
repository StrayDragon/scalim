from ....execution.key_normalization import normalize_key_normalization
from ....vendor.dataclassesx import replace
from .._public_template_sandbox import validate_public_template_sandbox
from .contracts import RunOptions


def normalize_public_run_options(options: RunOptions) -> RunOptions:
    template_sandbox = validate_public_template_sandbox(options.template_sandbox)
    key_normalization = normalize_key_normalization(options.key_normalization)
    max_workers = int(options.max_workers)
    if (
        template_sandbox == options.template_sandbox
        and key_normalization == options.key_normalization
        and max_workers == options.max_workers
    ):
        return options
    return replace(
        options,
        template_sandbox=template_sandbox,
        key_normalization=key_normalization,
        max_workers=max_workers,
    )


__all__ = ("normalize_public_run_options",)
