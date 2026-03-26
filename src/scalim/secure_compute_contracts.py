from __future__ import absolute_import

from abc import ABC, abstractmethod
from typing import Any, Tuple


class SecureComputeCalculatorContract(ABC):
    __slots__: Tuple[str, ...] = ()

    @abstractmethod
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


def is_secure_compute_calculator(value: object) -> bool:
    return isinstance(value, SecureComputeCalculatorContract)


__all__ = [
    "SecureComputeCalculatorContract",
    "is_secure_compute_calculator",
]
