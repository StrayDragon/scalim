from __future__ import absolute_import

from ..vendor.compact import StrEnum


class DerivedOverflowPolicy(StrEnum):
    ERROR = "error"
    TRUNCATE = "truncate"


class DedupOnConflictPolicy(StrEnum):
    ERROR = "error"
    FIRST = "first"
    LAST = "last"


__all__ = ()
