from typing import Iterator, List, Sequence, Tuple, Union

from .....planning.operators import LoadRefOperatorIr as LoadRefOp
from .....planning.operators import SupportedOperatorIr


def iter_operator_segments(
    operators: Sequence[SupportedOperatorIr],
) -> Iterator[Tuple[bool, Union[List[LoadRefOp], SupportedOperatorIr]]]:
    idx = 0
    while idx < len(operators):
        operator = operators[idx]
        if isinstance(operator, LoadRefOp):
            segment: List[LoadRefOp] = []
            while idx < len(operators):
                op = operators[idx]
                if not isinstance(op, LoadRefOp):
                    break
                segment.append(op)
                idx += 1
            yield True, segment
            continue

        yield False, operator
        idx += 1


__all__ = ()
