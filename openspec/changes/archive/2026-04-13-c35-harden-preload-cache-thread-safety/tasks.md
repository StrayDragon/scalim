## 1. Waiter path and inflight reads

- [x] 1.1 In `_get_or_load_waiter`, after `inflight.done.wait(...)`, read `inflight.error`/`inflight.value` under per-source lock

## 2. Mapping introspection under global lock

- [x] 2.1 `__iter__` returns snapshot under `_global_lock`
- [x] 2.2 `__len__` under `_global_lock`
- [x] 2.3 `__contains__` under `_global_lock`

## 3. Documentation

- [x] 3.1 Extended `PreloadCache` class docstring with thread-safety contract

## 4. Tests

- [x] 4.1 Existing concurrent tests cover `get_or_load` contention; `__iter__`/`__len__`/`__contains__` are now lock-protected

## 5. Verification

- [x] 5.1 Run `just qa` / `just test-gate`.
- [x] 5.2 Run `just openspec-check`.
