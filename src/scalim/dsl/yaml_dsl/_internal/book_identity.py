"""`Book` 运行时身份: `pathful` 与 `pathless`(`SSOT`).

说明:
- `BookConfig.path is not None` → `pathful`(版本化落盘 / `workbook` 后端)
- `BookConfig.path is None` → `pathless`(内存总线 / `sheetbook` 后端)
"""

from ..schema_dsl.models import BookConfig


def is_pathful_book(book: BookConfig) -> bool:
    """`IR` 身份: 是否存在版本化导出 `path`(规范化后)."""

    return book.path is not None


__all__ = ()
