import ast
import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Optional, Tuple, TypeVar

from scalim.dsl.yaml_dsl.compiler_frontend.lsp_support import load_yaml_mapping_text

_K = TypeVar("_K")
_V = TypeVar("_V")

_CacheKey = Tuple[str, int]

_DEFAULT_CACHE_MAXSIZE = 128
_CACHE_MAXSIZE_ENV = "SCALIM_YAML_DSL_LSP_CACHE_MAXSIZE"


def _parse_maxsize_env() -> int:
    raw = str(os.environ.get(_CACHE_MAXSIZE_ENV, "")).strip()
    if not raw:
        return _DEFAULT_CACHE_MAXSIZE
    try:
        maxsize = int(raw)
    except ValueError:
        return _DEFAULT_CACHE_MAXSIZE
    return max(0, maxsize)


class _InflightCacheError(RuntimeError):
    pass


class _InflightCacheProducedNoValueError(_InflightCacheError):
    def __init__(self) -> None:
        super().__init__("inflight cache produced no value")


class _Inflight(Generic[_V]):
    __slots__: Tuple[str, ...] = ("event", "exc", "value")

    event: threading.Event
    value: Optional[_V]
    exc: Optional[BaseException]

    def __init__(self) -> None:
        self.event = threading.Event()
        self.value = None
        self.exc = None


class _LRUCache(Generic[_K, _V]):
    maxsize: int
    _lock: threading.Lock

    def __init__(self, *, maxsize: int) -> None:
        self.maxsize = max(0, int(maxsize))
        self._lock = threading.Lock()
        self._data: "OrderedDict[_K, _V]" = OrderedDict()
        self._inflight: Dict[_K, _Inflight[_V]] = {}

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._inflight.clear()

    def get_or_compute(self, key: _K, compute: Callable[[], _V]) -> _V:
        if self.maxsize <= 0:
            return compute()

        with self._lock:
            cached = self._data.get(key)
            if cached is not None:
                self._data.move_to_end(key)
                return cached

            inflight = self._inflight.get(key)
            if inflight is None:
                inflight = _Inflight[_V]()
                self._inflight[key] = inflight
                is_owner = True
            else:
                is_owner = False

        if not is_owner:
            inflight.event.wait()
            if inflight.exc is not None:
                raise inflight.exc
            if inflight.value is None:
                raise _InflightCacheProducedNoValueError
            return inflight.value

        try:
            value = compute()
        except BaseException as exc:
            with self._lock:
                inflight.exc = exc
                inflight.event.set()
                self._inflight.pop(key, None)
            raise

        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

            inflight.value = value
            inflight.event.set()
            self._inflight.pop(key, None)
        return value


_text_cache: _LRUCache[_CacheKey, str] = _LRUCache(maxsize=_parse_maxsize_env())
_ast_cache: _LRUCache[_CacheKey, ast.Module] = _LRUCache(maxsize=_parse_maxsize_env())
_yaml_cache: _LRUCache[_CacheKey, Tuple[Dict[str, Any], Any, Any]] = _LRUCache(maxsize=_parse_maxsize_env())


def cache_maxsize() -> int:
    return int(_text_cache.maxsize)


def configure_cache(*, maxsize: int) -> None:
    for cache in (_text_cache, _ast_cache, _yaml_cache):
        cache.maxsize = max(0, int(maxsize))
        cache.clear()


def clear_caches() -> None:
    _text_cache.clear()
    _ast_cache.clear()
    _yaml_cache.clear()


def _cache_key_for_path(path: Path) -> Optional[_CacheKey]:
    try:
        stat = path.stat()
    except Exception:  # noqa: BLE001
        return None
    return (str(path), int(stat.st_mtime_ns))


def _read_text_uncached(path_str: str) -> str:
    return Path(path_str).read_text(encoding="utf-8")


def _read_text_cached_by_key(key: _CacheKey) -> str:
    path_str, _mtime_ns = key
    return _text_cache.get_or_compute(key, lambda: _read_text_uncached(path_str))


def read_text_cached(path: Path) -> str:
    key = _cache_key_for_path(path)
    if key is None:
        return path.read_text(encoding="utf-8")
    return _read_text_cached_by_key(key)


def parse_python_ast_cached(path: Path) -> ast.Module:
    key = _cache_key_for_path(path)
    if key is None:
        text = path.read_text(encoding="utf-8")
        return ast.parse(text)

    return _ast_cache.get_or_compute(key, lambda: ast.parse(_read_text_cached_by_key(key)))


def load_yaml_mapping_cached(path: Path) -> Tuple[Dict[str, Any], Any, Any]:
    key = _cache_key_for_path(path)
    if key is None:
        text = path.read_text(encoding="utf-8")
        return load_yaml_mapping_text(text, source_path=str(path), detect_duplicate_keys=True)

    path_str, _mtime_ns = key
    return _yaml_cache.get_or_compute(
        key,
        lambda: load_yaml_mapping_text(_read_text_cached_by_key(key), source_path=path_str, detect_duplicate_keys=True),
    )
