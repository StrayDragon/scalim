"""`Book` 级写入策略与预算(`Python` `SSOT`).

`YAML` 不再 `authoring` `write_defaults` / `xlsx_memory.budget`;缺省使用 `builtin` `defaults`.
公开构造函数仅接受 `StrEnum`(严格 `in`);内部/`IR` 仍使用 `builtin` `str`.
"""

from typing import TYPE_CHECKING, Dict, Mapping, Optional

from ...vendor.compact import StrEnum
from ...vendor.dataclassesx import dataclass, replace
from ...vendor.dataclassesx import field as dataclass_field
from .schema_dsl.models import BookBudgetConfig, BookWriteDefaultsConfig
from .schema_dsl.output_enums import (
    DEFAULT_BOOK_WRITE_ALIGN_BY,
    DEFAULT_BOOK_WRITE_HEADER_POLICY,
    DEFAULT_BOOK_WRITE_MODE,
    DEFAULT_BOOK_WRITE_ON_CONFLICT,
    DEFAULT_BOOK_WRITE_ON_MISMATCH,
)

if TYPE_CHECKING:
    from .schema_dsl.models import DemandConfig


class BookWriteMode(StrEnum):
    SHEET = "sheet"
    APPEND = "append"


class BookWriteAlignBy(StrEnum):
    FIELD_ID = "field_id"
    HEADER = "header"


class BookWriteHeaderPolicy(StrEnum):
    ONCE = "once"
    ALWAYS = "always"
    NEVER = "never"


class BookWriteOnMismatch(StrEnum):
    ERROR = "error"
    WARN = "warn"
    SKIP = "skip"


class BookWriteOnConflict(StrEnum):
    ERROR = "error"
    OVERWRITE = "overwrite"
    SKIP = "skip"


@dataclass(frozen=True)
class BookWritePolicy:
    """`Book` 级写入策略(`Python` `SSOT`)."""

    mode: BookWriteMode = BookWriteMode.SHEET
    align_by: BookWriteAlignBy = BookWriteAlignBy.FIELD_ID
    header_policy: BookWriteHeaderPolicy = BookWriteHeaderPolicy.ONCE
    on_mismatch: BookWriteOnMismatch = BookWriteOnMismatch.ERROR
    on_conflict: BookWriteOnConflict = BookWriteOnConflict.ERROR

    def __post_init__(self) -> None:
        if not isinstance(self.mode, BookWriteMode):
            msg = "BookWritePolicy.mode must be a BookWriteMode"
            raise TypeError(msg)
        if not isinstance(self.align_by, BookWriteAlignBy):
            msg = "BookWritePolicy.align_by must be a BookWriteAlignBy"
            raise TypeError(msg)
        if not isinstance(self.header_policy, BookWriteHeaderPolicy):
            msg = "BookWritePolicy.header_policy must be a BookWriteHeaderPolicy"
            raise TypeError(msg)
        if not isinstance(self.on_mismatch, BookWriteOnMismatch):
            msg = "BookWritePolicy.on_mismatch must be a BookWriteOnMismatch"
            raise TypeError(msg)
        if not isinstance(self.on_conflict, BookWriteOnConflict):
            msg = "BookWritePolicy.on_conflict must be a BookWriteOnConflict"
            raise TypeError(msg)

    def to_write_defaults_config(self) -> BookWriteDefaultsConfig:
        return BookWriteDefaultsConfig(
            mode=str(self.mode.value),
            align_by=str(self.align_by.value),
            header_policy=str(self.header_policy.value),
            on_mismatch=str(self.on_mismatch.value),
            on_conflict=str(self.on_conflict.value),
        )


@dataclass(frozen=True)
class BookBudgetPolicy:
    """`Book` 内存预算(`Python` `SSOT`). `None` = `unlimited`(无上限)."""

    max_sheets: Optional[int] = None
    max_total_cells: Optional[int] = None

    def __post_init__(self) -> None:
        if self.max_sheets is not None:
            if not isinstance(self.max_sheets, int) or isinstance(self.max_sheets, bool):
                msg = "BookBudgetPolicy.max_sheets must be an int or None"
                raise TypeError(msg)
            if int(self.max_sheets) < 1:
                msg = "BookBudgetPolicy.max_sheets must be >= 1 when set"
                raise ValueError(msg)
        if self.max_total_cells is not None:
            if not isinstance(self.max_total_cells, int) or isinstance(self.max_total_cells, bool):
                msg = "BookBudgetPolicy.max_total_cells must be an int or None"
                raise TypeError(msg)
            if int(self.max_total_cells) < 1:
                msg = "BookBudgetPolicy.max_total_cells must be >= 1 when set"
                raise ValueError(msg)

    def as_options_mapping(self) -> Optional[Mapping[str, int]]:
        if self.max_sheets is None and self.max_total_cells is None:
            return None
        out: Dict[str, int] = {}
        if self.max_sheets is not None:
            out["max_sheets"] = int(self.max_sheets)
        if self.max_total_cells is not None:
            out["max_total_cells"] = int(self.max_total_cells)
        # `resource_defs` 在启用 `budget` 时要求两个 `key` 都存在
        if "max_sheets" not in out or "max_total_cells" not in out:
            msg = (
                "BookBudgetPolicy requires both max_sheets and max_total_cells when enabling a budget "
                "(got max_sheets={!r}, max_total_cells={!r})"
            ).format(self.max_sheets, self.max_total_cells)
            raise ValueError(msg)
        return out


@dataclass(frozen=True)
class BookResourcePolicy:
    write: BookWritePolicy = dataclass_field(default_factory=BookWritePolicy)
    budget: BookBudgetPolicy = dataclass_field(default_factory=BookBudgetPolicy)

    def __post_init__(self) -> None:
        if not isinstance(self.write, BookWritePolicy):
            msg = "BookResourcePolicy.write must be a BookWritePolicy"
            raise TypeError(msg)
        if not isinstance(self.budget, BookBudgetPolicy):
            msg = "BookResourcePolicy.budget must be a BookBudgetPolicy"
            raise TypeError(msg)


@dataclass(frozen=True)
class ResourcesPolicy:
    """`Workflow`/`demand` 级资源策略(`Python` `SSOT`)."""

    books: Optional[Mapping[str, BookResourcePolicy]] = None

    def __post_init__(self) -> None:
        books = self.books
        if books is None:
            return
        if not isinstance(books, Mapping):
            msg = "ResourcesPolicy.books must be a mapping or None"
            raise TypeError(msg)
        normalized: Dict[str, BookResourcePolicy] = {}
        for book_id, policy in books.items():
            key = str(book_id).strip()
            if not key:
                msg = "ResourcesPolicy.books keys must be non-empty book ids"
                raise ValueError(msg)
            if not isinstance(policy, BookResourcePolicy):
                msg = "ResourcesPolicy.books[{!r}] must be a BookResourcePolicy".format(key)
                raise TypeError(msg)
            normalized[key] = policy
        object.__setattr__(self, "books", normalized or None)

    def write_policy_for(self, book_id: str) -> BookWritePolicy:
        books = self.books or {}
        policy = books.get(str(book_id))
        if policy is None:
            return BookWritePolicy()
        return policy.write

    def budget_policy_for(self, book_id: str) -> BookBudgetPolicy:
        books = self.books or {}
        policy = books.get(str(book_id))
        if policy is None:
            return BookBudgetPolicy()
        return policy.budget


def builtin_write_defaults_config() -> BookWriteDefaultsConfig:
    return BookWriteDefaultsConfig(
        mode=str(DEFAULT_BOOK_WRITE_MODE),
        align_by=str(DEFAULT_BOOK_WRITE_ALIGN_BY),
        header_policy=str(DEFAULT_BOOK_WRITE_HEADER_POLICY),
        on_mismatch=str(DEFAULT_BOOK_WRITE_ON_MISMATCH),
        on_conflict=str(DEFAULT_BOOK_WRITE_ON_CONFLICT),
    )


def resolve_write_defaults_config(
    *,
    book_id: str,
    resources_policy: Optional[ResourcesPolicy],
) -> BookWriteDefaultsConfig:
    if resources_policy is None:
        return builtin_write_defaults_config()
    return resources_policy.write_policy_for(str(book_id)).to_write_defaults_config()


def materialize_resources_policy_onto_books(
    config: "DemandConfig",
    resources_policy: Optional[ResourcesPolicy],
) -> "DemandConfig":
    """将 `Python` `ResourcesPolicy` 物化到 `DemandConfig.books` 的内部 `write_defaults`/`budget` 槽位.

    `YAML` 不再 `authoring` 这些字段;物化后供 `demand` 路径 `composition` / `effective_outputs` 读取.
    """
    if config.resources is None or not config.resources.books:
        return config

    next_books = {}
    for book_id, book in config.resources.books.items():
        write_cfg = resolve_write_defaults_config(book_id=str(book_id), resources_policy=resources_policy)
        budget_cfg = None
        if str(book.kind or "").strip() == "xlsx_memory":
            budget_policy = BookBudgetPolicy() if resources_policy is None else resources_policy.budget_policy_for(str(book_id))
            budget_mapping = budget_policy.as_options_mapping()
            if budget_mapping is not None:
                budget_cfg = BookBudgetConfig(
                    max_sheets=int(budget_mapping["max_sheets"]),
                    max_total_cells=int(budget_mapping["max_total_cells"]),
                )
        next_books[str(book_id)] = replace(book, write_defaults=write_cfg, budget=budget_cfg)

    next_resources = replace(config.resources, books=next_books)
    return replace(config, resources=next_resources)


__all__ = (
    "BookBudgetPolicy",
    "BookResourcePolicy",
    "BookWriteAlignBy",
    "BookWriteHeaderPolicy",
    "BookWriteMode",
    "BookWriteOnConflict",
    "BookWriteOnMismatch",
    "BookWritePolicy",
    "ResourcesPolicy",
    "builtin_write_defaults_config",
    "materialize_resources_policy_onto_books",
    "resolve_write_defaults_config",
)
