import contextlib
import io
import json
import logging

import pytest

from scalim.ob import structured_logging as sl


@contextlib.contextmanager
def _isolated_scalim_root_logger():
    root = logging.getLogger("scalim")
    orig_handlers = list(root.handlers)
    orig_level = int(root.level)
    orig_propagate = bool(root.propagate)
    try:
        root.handlers[:] = [h for h in root.handlers if getattr(h, "name", "") != "scalim.jsonl"]
        yield root
    finally:
        root.handlers[:] = orig_handlers
        root.setLevel(orig_level)
        root.propagate = orig_propagate


def test_assert_unique_abbreviations_raises_on_duplicates() -> None:
    with pytest.raises(RuntimeError):
        sl._assert_unique_abbreviations({"a": "x", "b": "x"})


def test_apply_profile_and_normalize_keys_support_lists() -> None:
    obj = {"context": [{"run_id": "r1"}]}
    compact = sl.apply_profile(obj, "compact")
    assert isinstance(compact, dict)
    assert "ctx" in compact

    verbose = sl.apply_profile(obj, "verbose")
    assert verbose == obj

    restored = sl.normalize_keys_to_full(compact)
    assert restored["context"][0]["run_id"] == "r1"


def test_format_exception_branches() -> None:
    assert sl._format_exception(None) is None
    assert sl._format_exception(True) is None

    direct = sl._format_exception(ValueError("boom"))
    assert direct and direct["error_type"] == "ValueError"

    tuple_exc = sl._format_exception((ValueError, ValueError("boom"), None))
    assert tuple_exc and tuple_exc["error_type"] == "ValueError"

    assert sl._format_exception(("bad",)) is None
    assert sl._format_exception(object()) is None
    assert sl._format_exception((None, None, None)) is None

    class _Unprintable(Exception):
        def __str__(self):  # type: ignore[no-untyped-def]
            raise TypeError("no str")

    unprintable = sl._format_exception(_Unprintable())
    assert unprintable and unprintable["error_message"] == "<unprintable>"


def test_jsonl_formatter_merges_extra_context_and_error() -> None:
    formatter = sl.JsonlFormatter(profile="compact")
    record = logging.LogRecord(
        name="scalim.tests.jsonl",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=(ValueError, ValueError("boom"), None),
        func=None,
        sinfo=None,
    )
    record.__dict__["scalim_fields"] = "not a dict"
    record.__dict__["scalim_ctx"] = {"workflow_node_id": "n1"}
    record.__dict__["scalim_error"] = {"error_message": "override"}

    with sl.log_context(run_id="r1"):
        text = formatter.format(record)

    parsed = sl.normalize_keys_to_full(json.loads(text))
    assert parsed["context"]["run_id"] == "r1"
    assert parsed["context"]["workflow_node_id"] == "n1"
    assert parsed["error"]["error_message"] == "override"


def test_install_jsonl_logging_chooses_stream_and_is_idempotent(capsys) -> None:
    with _isolated_scalim_root_logger():
        sl.install_jsonl_logging(stream_name="stdout", profile="compact")
        assert sl.is_jsonl_logging_installed() is True

        # idempotent
        sl.install_jsonl_logging(stream_name="stdout", profile="compact")
        assert sl.is_jsonl_logging_installed() is True

    _ = capsys.readouterr()


def test_log_context_finally_handles_empty_stack() -> None:
    with sl.log_context(run_id="r1"):
        sl._state().stack.clear()


def test_install_jsonl_logging_does_not_override_non_notset_level() -> None:
    with _isolated_scalim_root_logger() as root:
        root.setLevel(logging.DEBUG)
        sl.install_jsonl_logging(stream=io.StringIO(), profile="compact")
        assert int(root.level) == logging.DEBUG


def test_maybe_install_jsonl_logging_from_env(monkeypatch) -> None:
    with _isolated_scalim_root_logger():
        monkeypatch.setenv(sl.ENV_SCALIM_LOG_FORMAT, "jsonl")
        monkeypatch.setenv(sl.ENV_SCALIM_LOG_PROFILE, "verbose")
        monkeypatch.setenv(sl.ENV_SCALIM_LOG_STREAM, "stdout")
        sl.maybe_install_jsonl_logging_from_env()
        assert sl.is_jsonl_logging_installed() is True

    with _isolated_scalim_root_logger():
        monkeypatch.setenv(sl.ENV_SCALIM_LOG_FORMAT, "on")
        sl.maybe_install_jsonl_logging_from_env()
        assert sl.is_jsonl_logging_installed() is True


def test_emit_structured_accepts_ctx_mapping() -> None:
    with _isolated_scalim_root_logger():
        buf = io.StringIO()
        sl.install_jsonl_logging(stream=buf, profile="compact")
        logger = logging.getLogger("scalim.tests.emit")
        sl.emit_structured(logger, level=logging.INFO, kind="demo", message="m", ctx={"demand": "x"})
        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        assert lines


def test_normalize_helpers_handle_unknown_values() -> None:
    assert sl._normalize_bool_env("yes") is True
    assert sl._normalize_bool_env("0") is False
    assert sl._normalize_profile("VERBOSE") == "verbose"
    assert sl._normalize_profile("unknown") == "compact"
    assert sl._normalize_stream_name("stdout") == "stdout"
    assert sl._normalize_stream_name("garbage") == "stderr"
