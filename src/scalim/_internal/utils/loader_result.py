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
from typing import Any, Dict, cast

from ...vendor.compact import StrEnum
from .policy import (
    ensure_policy_enum,
    enum_values,
    normalize_token_lower_strip,
    parse_policy_value,
)


class LoaderResultPolicy(StrEnum):
    FULL = "full"
    SUMMARY = "summary"
    SAMPLE = "sample"
    NONE = "none"


LoaderResultPolicyValue = str
"""加载结果策略的规范化内置 `str` 值(用于运行时存储与 `state`/`wire` 边界)."""

_DEFAULT_LOADER_RESULT_POLICY = LoaderResultPolicy.FULL
LOADER_RESULT_POLICY_VALUES = enum_values(LoaderResultPolicy)

__all__ = ()


def format_loader_result_policy(policy: LoaderResultPolicy) -> LoaderResultPolicyValue:
    return policy.value


def parse_loader_result_policy(policy: object) -> LoaderResultPolicyValue:
    """从配置/状态边界(例如 `__setstate__`)解析并校验 `loader_result_policy`(封闭集合;快速失败)."""
    return parse_policy_value(
        LoaderResultPolicy,
        policy,
        label="loader_result_policy",
        default=_DEFAULT_LOADER_RESULT_POLICY,
        normalize=normalize_token_lower_strip,
        allow_empty=False,
    )


def normalize_loader_result_policy(policy: LoaderResultPolicy) -> LoaderResultPolicyValue:
    """公开 API: 严格只接受 `Enum`,并返回规范化后的内置 `str` 值."""
    enum_value = ensure_policy_enum(LoaderResultPolicy, policy, label="loader_result_policy")
    return format_loader_result_policy(enum_value)


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
