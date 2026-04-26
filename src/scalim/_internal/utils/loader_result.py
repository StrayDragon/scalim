# pragma: allow-cast-file loader result boundary typed narrowing
"""`loader_result_policy` 公共辅助函数.

为 `HookManager` 和 `ObserverManager` 提供统一的加载结果策略归一化、
摘要生成和采样逻辑.
"""

import contextlib
from collections.abc import Mapping as MappingABC
from collections.abc import Sequence as SequenceABC
from collections.abc import Set as AbstractSet
from collections.abc import Sized as SizedABC
from itertools import islice
from typing import Any, Dict, Union, cast

from ...vendor.compact import StrEnum


class LoaderResultPolicy(StrEnum):
    FULL = "full"
    SUMMARY = "summary"
    SAMPLE = "sample"
    NONE = "none"


LoaderResultPolicyLike = Union[str, LoaderResultPolicy]

_ALLOWED_LOADER_RESULT_POLICIES_LABEL = "full/summary/sample/none"

__all__ = ()


def normalize_loader_result_policy(policy: object) -> LoaderResultPolicy:
    """归一化并校验 `loader_result_policy` 字符串."""
    if isinstance(policy, LoaderResultPolicy):
        return policy
    if not isinstance(policy, str):
        msg = "loader_result_policy must be a str, got '{}'".format(type(policy).__name__)
        raise TypeError(msg)
    normalized = policy.strip().lower()
    if not normalized:
        msg = "loader_result_policy must not be empty; expected one of: {}".format(_ALLOWED_LOADER_RESULT_POLICIES_LABEL)
        raise ValueError(msg)
    try:
        return LoaderResultPolicy(normalized)
    except ValueError as exc:
        msg = "Unknown loader_result_policy: '{}'".format(policy)
        raise ValueError(msg) from exc


def summarize_loader_result(result: Any) -> Dict[str, Any]:
    """返回 `loader result` 的轻量摘要字典."""
    summary: Dict[str, Any] = {"type": type(result).__name__}
    if isinstance(result, SizedABC):
        with contextlib.suppress(Exception):
            summary["size"] = len(result)
    return summary


def sample_loader_result(result: Any, *, sample_size: int) -> Any:
    """返回 `loader result` 的大小受限采样.

    当结果类型不支持直接切片时,回退到 `summarize_loader_result`.
    """
    sample: Any = None
    if isinstance(result, MappingABC):
        mapping = cast("MappingABC[Any, Any]", result)  # pragma: allow-cast mapping typed narrowing
        sample = dict(islice(mapping.items(), sample_size))
    elif isinstance(result, list):
        items = cast("list[Any]", result)  # pragma: allow-cast list typed narrowing
        sample = items[:sample_size]
    elif isinstance(result, tuple):
        items = cast("tuple[Any, ...]", result)  # pragma: allow-cast tuple typed narrowing
        sample = list(items[:sample_size])
    elif isinstance(result, AbstractSet):
        sample = list(islice(result, sample_size))
    elif isinstance(result, (str, bytes)):
        sample = result[:sample_size]
    elif isinstance(result, SequenceABC):
        with contextlib.suppress(Exception):
            sequence = cast("SequenceABC[Any]", result)  # pragma: allow-cast sequence typed narrowing
            sample = list(sequence[:sample_size])
    if sample is None:
        return summarize_loader_result(result)
    return sample
