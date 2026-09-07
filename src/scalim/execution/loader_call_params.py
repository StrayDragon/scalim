from ..spec.ir.binding import BindingIr, LoaderCallContextIr
from ..typedefs import LoaderCallParams
from .runtime_bindings import RuntimeBindings


def build_loader_call_params(
    *,
    binding: BindingIr | None,
    context: LoaderCallContextIr,
    runtime_bindings: RuntimeBindings,
) -> LoaderCallParams:
    """为 `BindingIr` 渲染加载器调用参数.

    说明:
    - 静态 `IR` 仅携带参数模板(用于 YAML DSL)或 `params_builder_ref`(用于 `Python` DSL)的引用描述.
    - 执行阶段不做 `import`/解析;当绑定使用 `params_builder_ref` 时,会从 `RuntimeBindings` 获取已解析的构造器并调用.
    """

    if binding is None:
        return (), {}

    if binding.params_builder_ref is not None:
        params_builder = runtime_bindings.get_params_builder(context.source_id, binding.key_field)
        if params_builder is None:
            msg = f"Missing runtime params builder for source_id={context.source_id!r}, key_field={binding.key_field!r}"
            raise KeyError(msg)
        return params_builder(context)

    return binding.build_params(context)


__all__ = ("build_loader_call_params",)
