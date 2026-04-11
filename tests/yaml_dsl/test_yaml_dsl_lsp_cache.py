import ast
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from scalim_yaml_dsl_lsp import cache as lsp_cache
from tests.support.testing_utils import CI_TIMEOUT_S, event_wait, future_result


def _bump_mtime_ns(path: Path) -> None:
    stat = path.stat()
    os.utime(path, ns=(int(stat.st_atime_ns), int(stat.st_mtime_ns) + 1))


def test_read_text_cached_respects_mtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lsp_cache.configure_cache(maxsize=128)
    lsp_cache.clear_caches()

    path = tmp_path / "demo.txt"
    path.write_text("v1", encoding="utf-8")

    calls = {"count": 0}
    orig_read_text = Path.read_text

    def _counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            calls["count"] += 1
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    assert lsp_cache.read_text_cached(path) == "v1"
    assert lsp_cache.read_text_cached(path) == "v1"
    assert calls["count"] == 1

    path.write_text("v2", encoding="utf-8")
    _bump_mtime_ns(path)

    assert lsp_cache.read_text_cached(path) == "v2"
    assert calls["count"] == 2


def test_parse_python_ast_cached_respects_mtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lsp_cache.configure_cache(maxsize=128)
    lsp_cache.clear_caches()

    path = tmp_path / "demo.py"
    path.write_text("x = 1\n", encoding="utf-8")

    calls = {"count": 0}
    orig_parse = ast.parse

    def _counting_parse(*args, **kwargs):
        calls["count"] += 1
        return orig_parse(*args, **kwargs)

    monkeypatch.setattr(ast, "parse", _counting_parse)

    _ = lsp_cache.parse_python_ast_cached(path)
    _ = lsp_cache.parse_python_ast_cached(path)
    assert calls["count"] == 1

    path.write_text("x = 2\n", encoding="utf-8")
    _bump_mtime_ns(path)

    _ = lsp_cache.parse_python_ast_cached(path)
    assert calls["count"] == 2


def test_inflight_dedup_prevents_duplicate_reads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lsp_cache.configure_cache(maxsize=128)
    lsp_cache.clear_caches()

    path = tmp_path / "demo.txt"
    path.write_text("hello", encoding="utf-8")

    calls = {"count": 0}
    started = threading.Event()
    proceed = threading.Event()

    orig_read_text = Path.read_text

    def _slow_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            calls["count"] += 1
            started.set()
            event_wait(proceed, timeout_s=CI_TIMEOUT_S, label="proceed")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _slow_read_text)

    with ThreadPoolExecutor(max_workers=2) as executor:
        fut1 = executor.submit(lsp_cache.read_text_cached, path)
        event_wait(started, timeout_s=CI_TIMEOUT_S, label="started")
        fut2 = executor.submit(lsp_cache.read_text_cached, path)
        proceed.set()

        assert future_result(fut1, timeout_s=CI_TIMEOUT_S, label="fut1") == "hello"
        assert future_result(fut2, timeout_s=CI_TIMEOUT_S, label="fut2") == "hello"

    assert calls["count"] == 1
