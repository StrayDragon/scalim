"""`DSL` 家族包.

对外推荐入口统一为 `scalim.dsl.<dsl_name>`.

例如:
- `scalim.dsl.by_yaml`: `YAML` `DSL` 官方入口
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import by_yaml  # noqa: TC004

__all__ = ("by_yaml",)
