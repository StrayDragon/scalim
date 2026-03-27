from typing import List, Sequence, Set, Tuple


def ordered_unique_str(items: Sequence[object]) -> Tuple[str, ...]:
    """对输入序列做 `str()` 归一化后,去重并保序.

    语义:
    - 使用首次出现顺序
    - 去重依据为 `str(item)` 归一化后的键
    - 返回不可变 `Tuple[str, ...]` 作为稳定结果
    """

    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return tuple(out)


__all__ = []
