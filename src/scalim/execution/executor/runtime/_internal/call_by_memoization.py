import fnmatch
import json
import logging
import os
from collections import OrderedDict
from typing import Any, Dict, Hashable, List, Optional, Tuple

from ....._internal.loggingx import prefix
from ....._project_constants import (
    ENV_EXP_CALL_BY_MEMOIZE_ALLOW,
    ENV_EXP_CALL_BY_MEMOIZE_DENY,
    ENV_EXP_CALL_BY_MEMOIZE_LOG_STATS,
    ENV_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES,
)
from .....typedefs import FieldValue

_ENV_MAX_ENTRIES = ENV_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES
_ENV_ALLOW = ENV_EXP_CALL_BY_MEMOIZE_ALLOW
_ENV_DENY = ENV_EXP_CALL_BY_MEMOIZE_DENY
_ENV_LOG_STATS = ENV_EXP_CALL_BY_MEMOIZE_LOG_STATS

_DISABLE_MIN_CALLS_MULTIPLIER = 4
_DISABLE_MAX_HIT_RATE = 0.01


def _parse_csv_patterns(raw: str) -> Tuple[str, ...]:
    if not raw:
        return ()
    items: List[str] = []
    for part in str(raw).split(","):
        s = str(part).strip()
        if not s:
            continue
        items.append(s)
    return tuple(items)


def _parse_int_env_positive_or_zero(raw: str) -> int:
    value = 0
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return 0
    if value <= 0:
        return 0
    return value


def _parse_bool_env(raw: str) -> bool:
    normalized = str(raw or "").strip().lower()
    if not normalized:
        return False
    if normalized in ("1", "true", "yes", "y", "on"):
        return True
    if normalized in ("0", "false", "no", "n", "off"):
        return False
    return False


class CallByMemoizeFieldFilter:
    allow_patterns: Tuple[str, ...]
    deny_patterns: Tuple[str, ...]

    def __init__(self, *, allow_patterns: Tuple[str, ...], deny_patterns: Tuple[str, ...]) -> None:
        self.allow_patterns = tuple(allow_patterns or ())
        self.deny_patterns = tuple(deny_patterns or ())

    def allows(self, field_key: str) -> bool:
        key = str(field_key)
        for pat in self.deny_patterns:
            if fnmatch.fnmatchcase(key, pat):
                return False
        if not self.allow_patterns:
            return True
        return any(fnmatch.fnmatchcase(key, pat) for pat in self.allow_patterns)


class CallByMemoizationFieldCache:
    field_key: str
    max_entries: int
    disabled_reason: Optional[str]

    calls: int
    hits: int
    misses: int
    unhashable: int
    unique_inserts: int
    evictions: int
    disabled: int

    _cache: "OrderedDict[Hashable, FieldValue]"

    def __init__(self, field_key: str, *, max_entries: int) -> None:
        self.field_key = str(field_key)
        self.max_entries = int(max_entries)
        self.disabled_reason = None

        self.calls = 0
        self.hits = 0
        self.misses = 0
        self.unhashable = 0
        self.unique_inserts = 0
        self.evictions = 0
        self.disabled = 0

        self._cache = OrderedDict()

    def is_enabled(self) -> bool:
        return self.disabled_reason is None and self.max_entries > 0

    def _disable(self, reason: str) -> None:
        if self.disabled_reason is not None:
            return
        self.disabled_reason = str(reason or "disabled")
        self.disabled += 1
        self._cache.clear()

    def try_get(self, key: Hashable) -> Tuple[bool, FieldValue, bool]:
        """返回 `(hit, value, hashable)`."""

        self.calls += 1
        if not self.is_enabled():
            return False, None, False

        try:
            value = self._cache[key]
        except KeyError:
            self.misses += 1
            return False, None, True
        except TypeError:
            self.unhashable += 1
            return False, None, False

        self.hits += 1
        self._cache.move_to_end(key)
        return True, value, True

    def store_miss(self, *, key: Hashable, value: FieldValue) -> None:
        if not self.is_enabled():
            return

        self.unique_inserts += 1
        self._cache[key] = value
        self._cache.move_to_end(key)
        if len(self._cache) > self.max_entries:
            _ = self._cache.popitem(last=False)
            self.evictions += 1

        self._maybe_disable()

    def _maybe_disable(self) -> None:
        if self.evictions <= 0:
            return

        hashable_calls = self.hits + self.misses
        if hashable_calls < self.max_entries * _DISABLE_MIN_CALLS_MULTIPLIER:
            return
        hit_rate = float(self.hits) / float(hashable_calls)
        if hit_rate < _DISABLE_MAX_HIT_RATE:
            self._disable("low_hit_rate")

    def to_dict(self) -> Dict[str, Any]:
        hashable_calls = self.hits + self.misses
        hit_rate = None
        if hashable_calls > 0:
            hit_rate = round(float(self.hits) / float(hashable_calls), 6)
        return {
            "field_key": self.field_key,
            "max_entries": int(self.max_entries),
            "calls": int(self.calls),
            "hits": int(self.hits),
            "misses": int(self.misses),
            "unhashable": int(self.unhashable),
            "unique_inserts": int(self.unique_inserts),
            "evictions": int(self.evictions),
            "disabled_reason": self.disabled_reason,
            "hit_rate": hit_rate,
        }


class CallByMemoizationController:
    max_entries: int
    field_filter: CallByMemoizeFieldFilter
    log_stats: bool
    _field_caches: Dict[str, CallByMemoizationFieldCache]

    def __init__(
        self,
        *,
        max_entries: int,
        field_filter: CallByMemoizeFieldFilter,
        log_stats: bool,
    ) -> None:
        self.max_entries = int(max_entries)
        self.field_filter = field_filter
        self.log_stats = bool(log_stats)
        self._field_caches = {}

    def is_field_allowed(self, field_key: str) -> bool:
        return self.field_filter.allows(str(field_key))

    def get_or_create_field_cache(self, field_key: str) -> CallByMemoizationFieldCache:
        key = str(field_key)
        cache = self._field_caches.get(key)
        if cache is not None:
            return cache
        cache = CallByMemoizationFieldCache(key, max_entries=self.max_entries)
        self._field_caches[key] = cache
        return cache

    def build_summary(self, *, top_n: int = 20) -> Dict[str, Any]:
        fields = list(self._field_caches.values())
        fields.sort(key=lambda s: (-int(s.hits), -int(s.calls), str(s.field_key)))
        if top_n > 0:
            fields = fields[: int(top_n)]

        totals = {
            "fields": len(self._field_caches),
            "calls": 0,
            "hits": 0,
            "misses": 0,
            "unhashable": 0,
            "unique_inserts": 0,
            "evictions": 0,
            "disabled_fields": 0,
        }
        for stat in self._field_caches.values():
            totals["calls"] += int(stat.calls)
            totals["hits"] += int(stat.hits)
            totals["misses"] += int(stat.misses)
            totals["unhashable"] += int(stat.unhashable)
            totals["unique_inserts"] += int(stat.unique_inserts)
            totals["evictions"] += int(stat.evictions)
            if stat.disabled_reason is not None:
                totals["disabled_fields"] += 1

        return {
            "enabled": True,
            "max_entries": int(self.max_entries),
            "allow": list(self.field_filter.allow_patterns),
            "deny": list(self.field_filter.deny_patterns),
            "totals": totals,
            "fields": [s.to_dict() for s in fields],
        }

    def maybe_log_summary(self) -> None:
        if not self.log_stats:
            return
        if not self._field_caches:
            return
        payload = self.build_summary(top_n=20)
        logging.getLogger("scalim.performance").info(
            "%s探针: 无 `$ctx` 的 `call_by` 记忆化摘要: %s",
            prefix("performance"),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        )


def build_call_by_memoization_controller() -> Optional[CallByMemoizationController]:
    max_entries = _parse_int_env_positive_or_zero(os.environ.get(_ENV_MAX_ENTRIES) or "")
    if max_entries <= 0:
        return None

    allow_patterns = _parse_csv_patterns(os.environ.get(_ENV_ALLOW) or "")
    deny_patterns = _parse_csv_patterns(os.environ.get(_ENV_DENY) or "")
    log_stats = _parse_bool_env(os.environ.get(_ENV_LOG_STATS) or "")
    return CallByMemoizationController(
        max_entries=max_entries,
        field_filter=CallByMemoizeFieldFilter(allow_patterns=allow_patterns, deny_patterns=deny_patterns),
        log_stats=bool(log_stats),
    )


__all__ = ()
