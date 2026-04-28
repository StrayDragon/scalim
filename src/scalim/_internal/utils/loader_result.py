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
from typing import Any, Dict, Optional, cast

from ...vendor.compact.typing_extensionsx import Literal

LoaderResultPolicyValue = Literal["full", "summary", "sample", "none"]
"""加载结果策略的字符串字面量类型(对外配置/状态/序列化边界)."""

LoaderResultPolicyLike = Optional[LoaderResultPolicyValue]
"""加载结果策略入参类型(允许 `None` 走默认值)."""

_LOADER_RESULT_POLICY_FULL: LoaderResultPolicyValue = "full"
_LOADER_RESULT_POLICY_SUMMARY: LoaderResultPolicyValue = "summary"
_LOADER_RESULT_POLICY_SAMPLE: LoaderResultPolicyValue = "sample"
_LOADER_RESULT_POLICY_NONE: LoaderResultPolicyValue = "none"
_LOADER_RESULT_POLICY_VALUES = (
    _LOADER_RESULT_POLICY_FULL,
    _LOADER_RESULT_POLICY_SUMMARY,
    _LOADER_RESULT_POLICY_SAMPLE,
    _LOADER_RESULT_POLICY_NONE,
)
_LOADER_RESULT_POLICY_VALUES_LABEL = "full/summary/sample/none"

__all__ = ()


def normalize_loader_result_policy(policy: object) -> LoaderResultPolicyValue:
    """归一化并校验 `loader_result_policy`(封闭集合; `fail-fast`).

    约定:
    - `None` 走默认值 `full`
    - 支持大小写不敏感
    - 返回值为稳定内置 `str`,用于状态/序列化边界
    """
    if policy is None:
        return _LOADER_RESULT_POLICY_FULL

    if not isinstance(policy, str):
        msg = "loader_result_policy must be a str, got '{}'".format(type(policy).__name__)
        raise TypeError(msg)
    if type(policy) is not str:
        msg = "loader_result_policy must be a builtin str, got '{}'; expected one of: {}".format(
            type(policy).__name__,
            _LOADER_RESULT_POLICY_VALUES_LABEL,
        )
        raise TypeError(msg)

    normalized = policy.strip().lower()
    if not normalized:
        msg = "loader_result_policy must not be empty; expected one of: {}".format(_LOADER_RESULT_POLICY_VALUES_LABEL)
        raise ValueError(msg)

    if normalized == _LOADER_RESULT_POLICY_FULL:
        return _LOADER_RESULT_POLICY_FULL
    if normalized == _LOADER_RESULT_POLICY_SUMMARY:
        return _LOADER_RESULT_POLICY_SUMMARY
    if normalized == _LOADER_RESULT_POLICY_SAMPLE:
        return _LOADER_RESULT_POLICY_SAMPLE
    if normalized == _LOADER_RESULT_POLICY_NONE:
        return _LOADER_RESULT_POLICY_NONE

    msg = "Unknown loader_result_policy: {!r}; expected one of: {}".format(policy, _LOADER_RESULT_POLICY_VALUES_LABEL)
    raise ValueError(msg)


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
