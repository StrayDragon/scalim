import logging

from scalim._internal import loggingx


def test_loggingx_null_handler_is_idempotent() -> None:
    logger = logging.getLogger("scalim.tests.loggingx.null_handler")
    logger.handlers[:] = []

    loggingx._ensure_null_handler(logger)  # noqa: SLF001
    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)
    null_count = sum(1 for h in logger.handlers if isinstance(h, logging.NullHandler))

    loggingx._ensure_null_handler(logger)  # noqa: SLF001
    null_count2 = sum(1 for h in logger.handlers if isinstance(h, logging.NullHandler))
    assert null_count2 == null_count


def test_loggingx_get_logger_and_prefix() -> None:
    assert loggingx.get_logger().name == "scalim"
    assert loggingx.get_logger("schema").name == "scalim.schema"
    assert loggingx.prefix("") == "[scalim] "
    assert loggingx.prefix("schema") == "[scalim] schema: "


def test_loggingx_format_kv_basic_sorting_and_skip_none() -> None:
    assert loggingx.format_kv({"b": 2, "a": 1, "skip": None}) == "a=1, b=2"


def test_loggingx_format_kv_stringify_branches() -> None:
    assert loggingx.format_kv(list_val=[1, 2]) == "list_val=1,2"
    assert loggingx.format_kv(tuple_val=(3, 4)) == "tuple_val=3,4"
    assert loggingx.format_kv(tags=set(["b", "a"])) == "tags=a,b"
    assert loggingx.format_kv(meta={"a": 1}) == 'meta={"a": 1}'
    assert loggingx.format_kv(num=123) == "num=123"

    out_set_type_error = loggingx.format_kv(objs=set([object(), object()]))
    assert out_set_type_error.startswith("objs=")
    assert "object" in out_set_type_error

    out_dict_type_error = loggingx.format_kv(bad={object(): 1})
    assert out_dict_type_error.startswith("bad=")
    assert "object" in out_dict_type_error


def test_loggingx_bind_returns_adapter() -> None:
    logger = logging.getLogger("scalim.tests.loggingx.adapter")
    adapter = loggingx.bind(logger, run_id="r1")
    assert isinstance(adapter, logging.LoggerAdapter)
    assert adapter.extra["run_id"] == "r1"
