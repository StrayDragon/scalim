from typing import Any, Dict, Iterable, List, Mapping


def norm_result_only(result: Mapping[str, Any]) -> Mapping[str, Any]:
    return result


def norm_result_ctx_positional(result: Mapping[str, Any], ctx: object) -> Mapping[str, Any]:
    _ = ctx
    return result


def norm_result_ctx_kwonly(result: Mapping[str, Any], *, ctx: object) -> Mapping[str, Any]:
    _ = ctx
    return result


def norm_kwonly_result(*, result: Mapping[str, Any]) -> Mapping[str, Any]:
    return result


def should_retry_ok(exc: Exception, ctx: object) -> bool:
    _ = (exc, ctx)
    return True


def load_main_rows(flag: int) -> List[Dict[str, object]]:
    _ = flag
    return []


def load_main_rows_with_optional(flag: int, tag: str = "x") -> List[Dict[str, object]]:
    _ = (flag, tag)
    return []


def load_ref_table(ids: Iterable[int], field_keys: List[str]) -> Dict[int, Dict[str, object]]:
    _ = field_keys
    return {int(i): {"id": int(i)} for i in ids}


__all__ = [
    "load_main_rows",
    "load_main_rows_with_optional",
    "load_ref_table",
    "norm_kwonly_result",
    "norm_result_ctx_kwonly",
    "norm_result_ctx_positional",
    "norm_result_only",
    "should_retry_ok",
]
