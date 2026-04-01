import sys

if sys.version_info[:2] >= (3, 7):
    from dataclasses import (
        MISSING,
        Field,
        FrozenInstanceError,
        InitVar,
        asdict,
        astuple,
        dataclass,
        field,
        fields,
        is_dataclass,
        make_dataclass,
        replace,
    )
else:
    from ._backport import (  # type: ignore[no-redef]
        MISSING,
        Field,
        FrozenInstanceError,
        InitVar,
        asdict,
        astuple,
        dataclass,
        field,
        fields,
        is_dataclass,
        make_dataclass,
        replace,
    )


__all__ = (
    "MISSING",
    "Field",
    "FrozenInstanceError",
    "InitVar",
    "asdict",
    "astuple",
    "dataclass",
    "field",
    "fields",
    "is_dataclass",
    "make_dataclass",
    "replace",
)
