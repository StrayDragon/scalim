import re
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from ....workflow.loaders import sheetbook_sheet_rows
from ..reference_syntax import BUILTIN_CALLABLE_REFERENCE_PREFIX
from .errors import ScalimResolverError

_BUILTIN_ID_RE = re.compile(r"^[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*$")

_DEFAULT_BUILTIN_CALLABLES_BY_ID: Dict[str, Callable[..., Any]] = {
    "workflow/sheetbook_sheet_rows": sheetbook_sheet_rows,
}

_DEFAULT_PUBLIC_BUILTIN_CALLABLE_IDS: Tuple[str, ...] = ("workflow/sheetbook_sheet_rows",)


def is_builtin_callable_reference(reference: str) -> bool:
    raw = str(reference or "").strip()
    if not raw.startswith(BUILTIN_CALLABLE_REFERENCE_PREFIX):
        return False
    builtin_id = raw[len(BUILTIN_CALLABLE_REFERENCE_PREFIX) :]
    return bool(builtin_id) and _BUILTIN_ID_RE.fullmatch(builtin_id) is not None


def parse_builtin_callable_id(reference: str) -> str:
    raw = str(reference or "").strip()
    if not raw.startswith(BUILTIN_CALLABLE_REFERENCE_PREFIX):
        msg = "Not a builtin callable reference: {!r}".format(reference)
        raise ScalimResolverError(msg)
    builtin_id = raw[len(BUILTIN_CALLABLE_REFERENCE_PREFIX) :]
    if not builtin_id:
        msg = "Invalid builtin callable reference {!r}: missing <id> after '{}'".format(reference, BUILTIN_CALLABLE_REFERENCE_PREFIX)
        raise ScalimResolverError(msg)
    if _BUILTIN_ID_RE.fullmatch(builtin_id) is None:
        msg = "Invalid builtin callable id {!r} in reference {!r}".format(builtin_id, reference)
        raise ScalimResolverError(msg)
    return builtin_id


def list_builtin_callable_ids() -> Tuple[str, ...]:
    return tuple(sorted(_DEFAULT_BUILTIN_CALLABLES_BY_ID.keys()))


def list_public_builtin_callable_ids() -> Tuple[str, ...]:
    return tuple(sorted(_DEFAULT_PUBLIC_BUILTIN_CALLABLE_IDS))


def resolve_builtin_callable_reference(
    reference: str,
    *,
    callables_by_id: Optional[Mapping[str, Callable[..., Any]]] = None,
    public_ids: Optional[Sequence[str]] = None,
) -> Callable[..., Any]:
    builtin_id = parse_builtin_callable_id(reference)
    fn = None
    if callables_by_id is not None:
        fn = callables_by_id.get(builtin_id)
    if fn is None:
        fn = _DEFAULT_BUILTIN_CALLABLES_BY_ID.get(builtin_id)
    if fn is not None:
        return fn

    available_ids = list_public_builtin_callable_ids() if public_ids is None else tuple(public_ids)
    available = ", ".join("{}{}".format(BUILTIN_CALLABLE_REFERENCE_PREFIX, item) for item in sorted(available_ids))
    msg = "Unknown builtin callable id {!r} (reference={!r}). Available ids (public): {}".format(
        builtin_id,
        reference,
        available or "<none>",
    )
    raise ScalimResolverError(msg)


__all__ = [
    "is_builtin_callable_reference",
    "list_builtin_callable_ids",
    "list_public_builtin_callable_ids",
    "parse_builtin_callable_id",
    "resolve_builtin_callable_reference",
]
