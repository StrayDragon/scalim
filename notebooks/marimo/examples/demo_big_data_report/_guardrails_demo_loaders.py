from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from collections import UserDict
from types import MappingProxyType, SimpleNamespace


class _GetItemRow:
    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = dict(data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


@dataclass(frozen=True)
class _MainRowObj:
    ref_id: int
    a: str
    b: int


@dataclass(frozen=True)
class _RefRowObj:
    value: str


def load_guardrails_demo_main_rows() -> List[Any]:
    """运行期 `guardrails` + `extract_field` 契约演示用的主表行数据.

    这些行刻意混合多种“像行一样”的数据形状:
    - `dict`
    - `Mapping`(非 `dict`): `UserDict` / `MappingProxyType`
    - 属性对象: `SimpleNamespace` / `dataclass`
    - `__getitem__` 鸭子类型
    """
    return [
        {"ref_id": 1, "a": "1", "b": 2},
        UserDict({"ref_id": 2, "a": "2", "b": 4}),
        MappingProxyType({"ref_id": 3, "a": "3", "b": 0}),
        SimpleNamespace(ref_id=4, a="4", b=8),
        _MainRowObj(ref_id=5, a="5", b=10),
        _GetItemRow({"ref_id": 999, "a": "6", "b": 12}),
        {"ref_id": 1, "a": "bad", "b": 14},
        {"ref_id": 2, "a": "7"},
    ]


def load_guardrails_demo_ref_table(ids: Optional[List[int]] = None) -> Dict[int, Any]:
    """演示中 `relation` 字段使用的引用表加载器.

    Returns:
        一个映射:`ref_id` -> `row_data`(其中 `row_data` 也会混合多种形状)
    """
    full: Dict[int, Any] = {
        1: UserDict({"value": "U1"}),
        2: MappingProxyType({"value": "P2"}),
        3: SimpleNamespace(value="S3"),
        4: _RefRowObj(value="D4"),
        5: _GetItemRow({"value": "G5"}),
    }
    if ids is None:
        return full
    return {k: full[k] for k in ids if k in full}
