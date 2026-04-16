from ....vendor.dataclassesx import replace
from .._public_template_sandbox import validate_public_template_sandbox
from .contracts import DemandRunOptions


def normalize_public_demand_run_options(options: DemandRunOptions) -> DemandRunOptions:
    """公开 `YAML` `DSL` 运行期契约在 `__post_init__` 中完成规范化/校验.

    该辅助函数为调用方提供一个统一的规范化边界,避免直接依赖底层规范化工具的实现细节.
    """

    template_sandbox = validate_public_template_sandbox(options.template.template_sandbox)
    if template_sandbox == options.template.template_sandbox:
        return options
    return replace(
        options,
        template=replace(
            options.template,
            template_sandbox=template_sandbox,
        ),
    )


__all__ = ("normalize_public_demand_run_options",)
