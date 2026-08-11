# Proposal: output write layout advisory

> 一句话描述: 在 `run_stats` / bench 观测中输出写出布局 **建议**（如宽表可试 IR 列式 WINDOW），默认不改写出行为；opt-in 自动切换另案且须 RSS 门控。

> **状态（2026-08-11）**：设计稿；依赖 D1 矩阵口径与（理想）D3 layout 命名；禁止静默 auto。

## Why

内存优先下「自主」不应等于静默改 sink：误切 HOLD↔WINDOW / 行↔列会改变峰与语义可解释性。  
需要先有 **可观测建议**，让运维/集成方自己决定是否改 `DemandRunRuntimeOptions` / IR。

## What Changes（设计方向）

1. **建议载荷**（候选挂在 `run_stats.notes` 或 `outputs[].hints`）：
   - `suggested_write_layout`：如 `column_window` / `row_stream` / `null`
   - `reason`：短码，如 `wide_excel_peak_risk`（基于 fields×rows 或已观测 peak 代理）
   - **绝不**在默认路径改 sink
2. **触发启发式（初稿，须用合成证据校准）**：
   - IR excel 列 HOLD 且 `n_fields * n_rows` 超阈值 → 建议 WINDOW
   - YAML composition 行式 → 建议文案指向「若峰不可接受，迁 IR 列式+WINDOW」，**不**建议设 residency（会 fail-fast）
3. **开关**：仅 `bench` / `bench_plus` 或显式 opt-in flag；`baseline` 无建议噪声
4. **日后 auto**（不在本草案）：单独 change；必须用户 opt-in + 峰值 RSS 不劣于基线 + 值等价

## 非目标

- 默认自动切换 layout
- YAML 配置阈值
- 与 memo / overlap cache 绑定

## Capabilities

### New Capabilities

- `observability-output-write-layout-advisory`：建议 schema 与「不改行为」契约

### Modified Capabilities

- `performance-observability` / run_stats：可选 hints 字段

## Impact

- 自主性：人/agent 可读建议后显式改 Python options
- 平衡：零默认行为变化；观测税须在 mid shape 上可接受（对齐 c50 税门控精神）
- 转正门控：建议文案对 composition 路径不得指向无效 WINDOW 设置；snapshot 测试

## 依赖

- D1 决策矩阵（已文档化）
- D3 layout 命名（若已落地则建议枚举与之对齐；否则用稳定字符串码）
