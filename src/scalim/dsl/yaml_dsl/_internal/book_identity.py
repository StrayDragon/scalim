"""`Book` 运行时身份: `pathful` 与 `pathless`(`SSOT`).

说明:
- `BookConfig.path is not None` → `pathful`(版本化落盘 / `workbook` 后端)
- `BookConfig.path is None` → `pathless`(内存总线 / `sheetbook` 后端)
- `kind=xlsx_file|xlsx_memory` 仅作过渡期 `wire`/`shim`, `MUST NOT` 再当长期身份 `SSOT`
"""

from ..schema_dsl.models import BookConfig

LEGACY_KIND_PATHFUL = "xlsx_file"
LEGACY_KIND_PATHLESS = "xlsx_memory"


def is_pathful_book(book: BookConfig) -> bool:
    """`IR` 身份: 是否存在版本化导出 `path`(规范化后)."""

    return book.path is not None


def legacy_kind_shim(*, pathful: bool) -> str:
    """由 `path` 有无派生的 `deprecated` `kind` 字符串(兼容旧断言 / `options`)."""

    return LEGACY_KIND_PATHFUL if pathful else LEGACY_KIND_PATHLESS


__all__ = ()
