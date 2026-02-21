from collections.abc import Iterator, Sequence
from typing import cast

from .....planning.operators import LoadRefOperatorIr as LoadRefOp
from .....planning.operators import SupportedOperatorIr


def iter_operator_segments(
    operators: Sequence[SupportedOperatorIr],
) -> Iterator[tuple[bool, object]]:
    idx = 0
    while idx < len(operators):
        operator = operators[idx]
        if isinstance(operator, LoadRefOp):
            segment: list[LoadRefOp] = []
            while idx < len(operators) and isinstance(operators[idx], LoadRefOp):
                segment.append(cast("LoadRefOp", operators[idx]))
                idx += 1
            yield True, segment
            continue

        yield False, operator
        idx += 1


__all__ = [
    "iter_operator_segments",
]
