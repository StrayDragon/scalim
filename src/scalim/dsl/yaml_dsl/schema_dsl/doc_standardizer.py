"""`JSON Schema` 文档标准化 `hook`(内部,仅生成期使用).

说明:
- `schema` 文档标准化属于生成期/开发期能力,实现位于可选依赖 `scalim-misc`.
- 主包仅提供 `ImportError-safe` 的 `hook`;当未安装 `scalim-misc` 时必须 `no-op`.
- 运行时(编译/校验/运行/工作流)不依赖该 `hook`.
"""

import importlib
from typing import Any, Callable, Dict, Optional, Sequence

Schema = Dict[str, Any]
StandardizeFn = Callable[..., Any]


def load_schema_doc_standardizer_impl() -> Optional[StandardizeFn]:
    """尝试加载 `schema` 文档标准化实现.

    返回:
    - `scalim-misc` 可用: 返回 `standardize_schema_docs` 实现
    - `scalim-misc` 缺失: 返回 `None`
    """

    try:
        mod = importlib.import_module("scalim_misc.yaml_schema_doc_standardizer")
    except ImportError:
        return None

    fn = getattr(mod, "standardize_schema_docs", None)  # pragma: allow-dynattr plugin: schema docs standardizer optional hook
    if callable(fn):
        return fn
    return None


def maybe_standardize_schema_docs(
    schema: Schema,
    *,
    fixture_paths: Optional[Sequence[str]] = None,
) -> Schema:
    """对 `schema` 应用文档标准化(若插件可用)."""

    impl = load_schema_doc_standardizer_impl()
    if impl is None:
        return schema
    return impl(schema, fixture_paths=fixture_paths)


__all__ = ("load_schema_doc_standardizer_impl", "maybe_standardize_schema_docs")
