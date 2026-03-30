from typing import Any, Dict, Optional

NOT_CALLABLE = 1


def dummy_main_loader(**_kwargs):  # type: ignore[no-untyped-def]
    return []


def echo(value):  # type: ignore[no-untyped-def]
    return value


def add(a, b=0):  # type: ignore[no-untyped-def]
    return a + b


def status_text(status, *, ok_text="ok", bad_text="bad", ctx=None):  # type: ignore[no-untyped-def]
    prefix = ok_text if status else bad_text
    if ctx is None:
        return prefix
    return "{}:{}:{}".format(prefix, ctx.row_id, ctx.batch_num)


def sum_values(values: Dict[str, Any], *, key_a: str, key_b: str):  # type: ignore[no-untyped-def]
    return values.get(key_a) + values.get(key_b)


def needs_ctx_attr(row_id: Any) -> Any:
    return row_id


def maybe_ctx(ctx: Optional[Any] = None) -> str:
    return "has" if ctx is not None else "none"
