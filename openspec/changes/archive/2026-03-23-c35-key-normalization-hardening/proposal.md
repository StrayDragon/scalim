## Why

`key_normalization` 已作为实验性能力落地,但仍存在一些“上线后才会遇到”的边界风险: 一类是提示/诊断在默认观测配置下可能不够可见,另一类是 loader/cached mapping 的 key 口径与字符串规范化的交互在极端情况下容易踩坑(例如 collision 或实现方返回的 key 口径不一致).

本变更用于把这些风险收敛为明确的“可选增强/可控开关”,避免在后续版本中以隐性行为变更的方式修补.

## As-Is 调研（根因 + 最小复现）

### 1) EXPERIMENTAL 提示在默认配置下可能“完全不可见”

- 触发点在运行入口：`src/scalim/execution/run_ir.py` 会在 `key_normalization != "raw"` 时调用 `InstrumentationHub.emit_diagnostic_warning(..., sample_once=True)` 发出 `EXPERIMENTAL` 文案。
- 但 `emit_diagnostic_warning` 在 **无 observer/hook 且未启用 fallback logger** 的情况下会直接返回，不会有任何 stderr/log 输出：`src/scalim/ob/hub.py`。

最小复现思路（不依赖外部观察者）：

1. 构造一个最小 `DemandIr + ExecutionRequest(key_normalization="force_str")` 并调用 `run_ir(...)`。
2. 不注册任何 observer/hook，且不显式开启 fallback logger。
3. 预期：stderr/日志中应出现一次 `EXPERIMENTAL: key_normalization='force_str' ...`。
4. 实际：不会出现（提示被“无人订阅”路径吞掉）。

### 2) cached/preload mapping 的 str-view collision 当前一律 fail-fast

- `ExecutionRuntime.get_cached_source_mapping()` 在构建“稳定字符串 key space”视图时，遇到多个 key 规范化到同一个 stable string 会直接 `raise ValueError`：`src/scalim/execution/executor/runtime/runtime.py`。
- 这在 `auto_str/force_str` 下很常见（例如 loader 同时返回 `1` 与 `"1"`、或 tuple 里出现 `"001"`/`1` 等），且当前没有“values 相等可合并继续”的开箱即用行为。

## What Changes

- 强化 `key_normalization` 的“实验性提示”可见性: 即使未配置任何 observer/hook/日志观察者,也能在一次运行内明确看到 `EXPERIMENTAL` 提示(一次去重).
- 增补 `key_normalization` 的 loader/cached mapping 边界诊断:
  - 当 loader 返回的 mapping key 口径与当前匹配口径不一致时,提供可诊断的告警/错误(不泄露明细 key 值).
  - 当 mapping 规范化发生 key collision 时,提供更明确的错误上下文(不泄露明细 key 值),并将默认处理优化为: values 相等则合并继续+告警,values 不相等则 fail-fast.

实现建议（可维护性优先）：

- EXPERIMENTAL 提示的默认可见通道推荐使用 `warnings.warn(..., category=ScalimExperimentalWarning)` 作为兜底（不依赖 observer/hook/fallback logger），并保持一次运行去重。
- collision/mismatch 的诊断信息必须统一走“redacted context”构造，避免异常/告警意外包含 raw key 的 `repr`。

## Sequencing / Dependencies

- 建议作为诊断/治理类基线尽早落地（可与安全类 changes 并行），用于把“默认不可见的提示”升级为可回归的失败信号，降低后续迭代定位成本。

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
