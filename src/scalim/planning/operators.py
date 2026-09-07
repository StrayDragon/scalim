# region imports

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .._internal.strenum import StrEnum

# endregion

if TYPE_CHECKING:
    from ..spec.ir import LookupStepIr


class OperatorType(StrEnum):
    """算子类型.

    说明:
    - `PlanBuilder` 仅生成规划层核心算子: `LOAD` / `LOAD_REF` / `COMPUTE`.
    - 写出/释放等算子类型 (`WRITE_*` / `RELEASE`) 属于执行编排范畴, 不由 `PlanBuilder` 产出.
    """

    LOAD = "load"
    LOAD_REF = "load_ref"
    COMPUTE = "compute"
    WRITE_COLUMN = "write_column"
    WRITE_ROW = "write_row"
    RELEASE = "release"


@dataclass(frozen=True)
class LoadOperatorIr:
    """加载主数据算子"""

    operator_id: str
    operator_type: str
    source_id: str
    field_keys: tuple[str, ...]
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    is_primary: bool = False


@dataclass(frozen=True)
class LoadRefOperatorIr:
    """关联加载算子:包含完整的 `LookupStepIr` 链"""

    operator_id: str
    operator_type: str
    source_id: str
    field_key: str
    lookup_steps: "tuple[LookupStepIr, ...]"
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    use_cache: bool = False


@dataclass(frozen=True)
class ComputeOperatorIr:
    """计算派生字段算子"""

    operator_id: str
    operator_type: str
    field_key: str
    input_fields: tuple[str, ...]
    depends_on: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class WriteColumnOperatorIr:
    """列写入算子"""

    operator_id: str
    operator_type: str
    field_key: str
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    can_release_after: bool = False


@dataclass(frozen=True)
class WriteRowOperatorIr:
    """行写入算子"""

    operator_id: str
    operator_type: str
    target_fields: tuple[str, ...]
    depends_on: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReleaseOperatorIr:
    """释放内存算子"""

    operator_id: str
    operator_type: str
    field_key: str
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""


SupportedOperatorIr = (
    LoadOperatorIr | LoadRefOperatorIr | ComputeOperatorIr | WriteColumnOperatorIr | WriteRowOperatorIr | ReleaseOperatorIr
)

PlanOperatorIr = LoadOperatorIr | LoadRefOperatorIr | ComputeOperatorIr

__all__ = (
    "ComputeOperatorIr",
    "LoadOperatorIr",
    "LoadRefOperatorIr",
    "OperatorType",
    "PlanOperatorIr",
    "ReleaseOperatorIr",
    "SupportedOperatorIr",
    "WriteColumnOperatorIr",
    "WriteRowOperatorIr",
)
