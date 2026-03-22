## Why

`key_normalization` 已作为实验性能力落地,但仍存在一些“上线后才会遇到”的边界风险: 一类是提示/诊断在默认观测配置下可能不够可见,另一类是 loader/cached mapping 的 key 口径与字符串规范化的交互在极端情况下容易踩坑(例如 collision 或实现方返回的 key 口径不一致).

本变更用于把这些风险收敛为明确的“可选增强/可控开关”,避免在后续版本中以隐性行为变更的方式修补.

## What Changes

- 强化 `key_normalization` 的“实验性提示”可见性: 即使未配置任何 observer/hook/日志观察者,也能在一次运行内明确看到 `EXPERIMENTAL` 提示(一次去重).
- 增补 `key_normalization` 的 loader/cached mapping 边界诊断:
  - 当 loader 返回的 mapping key 口径与当前匹配口径不一致时,提供可诊断的告警/错误(不泄露明细 key 值).
  - 当 cached mapping 规范化发生 key collision 时,提供更明确的错误上下文(不泄露明细 key 值),并评估是否需要可选的 collision 策略(仍以 fail-fast 为默认).

## Capabilities

### New Capabilities

### Modified Capabilities

- `key-normalization`: 增补“实验性提示可见性”的 hard requirement,并补齐 loader/cached mapping 的诊断与 collision 边界要求.

## Impact

- 影响的规范:
  - `openspec/specs/key-normalization/spec.md`
- 影响的代码(预估范围,非最终实现清单):
  - `src/scalim/execution/run_ir.py`(`EXPERIMENTAL` 提示策略)
  - `src/scalim/ob/hub.py`/`src/scalim/ob/observability.py`(fallback logger/告警落地口径,若选择复用)
  - `src/scalim/execution/executor/operators/load_ref/`(loader mapping 口径诊断/错误)

