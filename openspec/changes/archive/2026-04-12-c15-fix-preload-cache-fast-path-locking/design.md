## Context

`PreloadCache` 在实现与注释中以“线程安全的 preload_forever 缓存容器”为定位（见 `src/scalim/execution/preload_cache.py` 内的类说明）。在该契约下，调用方会自然假设：

- 多线程并发调用 `PreloadCache.get_or_load()` 是安全的；
- cache hit 快路径也不会因竞态导致异常或不一致的可观测行为。

当前实现为了在 guardrail 关闭时减少锁开销，引入了一个无锁 fast-path：当 `signature_guardrail` 关闭（`digest is None`）且 `source_id` 已在 `_data` 中时，直接从 `_data` 读并返回。

问题在于：写路径会在 per-source lock 下写入 `_data[source_id] = value`，而无锁 fast-path 会在不持锁时执行 `source_id in self._data` 与 `self._data[source_id]` 的组合读。在“并发读 + 并发写 dict”的组合下，系统并不承诺线程安全；在极端调度下可能出现 `KeyError`（成员检查与索引读取之间发生切换/删除）或其它非确定性行为，从而破坏“线程安全容器”的定位并制造 CI/线上偶现。

约束：

- 运行时保持 Python 3.6 兼容；
- 既有 `get_or_load()` 的 in-flight 去重与“load_fn 不在锁内执行”的护栏不改变。

## Goals / Non-Goals

**Goals:**

- 让 `PreloadCache.get_or_load()` 的 cache hit 路径满足线程安全语义：不再出现由无锁 dict 读写竞态导致的异常或不一致行为
- 行为保持不变：key 仍按 `source_id` 去重，in-flight 等语义不变
- 以最小改动完成 fix-0 级别修复

**Non-Goals:**

- 不追求保留无锁 fast-path 的微优化（收益有限且易引入新的维护风险）
- 不改变 signature guardrail 的语义与配置接口

## Decisions

### 1) 移除无锁 fast-path，所有 `_data[source_id]` 的读写统一走同一把 per-source lock

采用提案推荐的最简单方案：

- 删除 guardrail 关闭时的无锁 hit fast-path
- 对 cache hit 的检查与取值统一置于 `lock = self._lock_for(source_id)` 的 `with lock:` 临界区内执行

这样可保证 `_data` 的“成员检查 + 取值”与写路径在同一把锁下串行化，消除读写竞态窗口，并让实现与“线程安全容器”的契约一致。

### 2) 保持 load_fn 的锁外执行与 in-flight 去重不变

本修复只收敛 `_data` 的读路径同步策略，不改变既有结构性护栏：

- `load_fn()` 仍 MUST 不在保护缓存状态的互斥锁内执行（避免外部回调在锁内执行）
- in-flight 去重仍由既有机制保障（同一 `source_id` 并发 miss 最多一个真实 load）

## Risks / Trade-offs

- **性能回退（可接受）**：cache hit 将增加一次 per-source lock 开销。但 `get_or_load` 通常以 source 维度调用（不是逐行热路径），且 per-source 锁竞争范围窄；相比线程安全与可维护性，该开销可接受。
- **实现遗漏导致语义漂移**：若误把 `load_fn` 放进锁内会违反“外部回调不得在锁内执行”的护栏；需用回归测试与 code review 明确锁边界。

## Migration Plan

- 无需迁移：仅内部并发语义修正，不改变对外 API/配置。

## Open Questions

- 无。若未来确实需要再次优化 hit 快路径，可在确保线程安全的前提下引入“乐观读取 + 回退持锁”的局部化方案，但不在本 fix-0 范围内。

