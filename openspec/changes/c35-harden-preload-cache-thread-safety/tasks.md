## 1. Waiter path and inflight reads

- [ ] 1.1 In `src/scalim/execution/preload_cache.py`, after `inflight.done.wait(...)`, read `inflight.error` / `inflight.value` and any `_data` fallback only while holding the per-source lock (align with existing locked `_data` reads).

## 2. Mapping introspection under global lock

- [ ] 2.1 Implement `__iter__` with `self._global_lock` and return an iterator over a snapshot (e.g. `list(self._data.keys())`).
- [ ] 2.2 Implement `__len__` under `self._global_lock`.
- [ ] 2.3 Implement `__contains__` under `self._global_lock` (or equivalent consistent locking) per proposal.

## 3. Documentation

- [ ] 3.1 Extend the `PreloadCache` class docstring with thread-safety contract and lock roles (per-source vs global).

## 4. Tests

- [ ] 4.1 Add concurrent tests: multiple threads calling `get_or_load` while others iterate / query `len` / `__contains__` on the same cache instance.

## 5. Verification

- [ ] 5.1 Run `just qa` / `just test-gate`.
- [ ] 5.2 Run `just openspec-check`.
