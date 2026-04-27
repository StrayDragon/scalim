## Why

当前线上/日常主要场景并不依赖 `viz`（开发偶尔用）且 YAML 解析/导入也不是瓶颈；真实热点集中在 **execution 热路径**（尤其 `LoadRef` + `BatchContext` 读写 + 字段提取）。

补充上下文：生产/主要用例中 `LoadRef` 绑定模式以 `keys` 为主；`rows` 模式存在但较少使用（且更难在业务侧落地）。因此本 change 的优化优先覆盖 `keys` 热路径，`rows` 主要以“不回归”为目标。

基于本仓库自带的自生成大数据用例 `demo_big_data_report`（`scale=stress`，10k rows，`targets=relations`，`batch_size=100`）做本地 profiling（cProfile / memray / py-spy）后确认：
- CPU 主要消耗在 `DenseBatchContext` 的 `set_field_value/get_field_value`、`LoadRef` 写回链路（`_write_ref_fields/_resolve_ref_field_value`）以及字段提取（`extract_field_segments`）等常数项上。
- 内存分配热点与 `LoadRef` 的 key normalize cache（`normalize_key` 路径创建大量小对象）与 `init_first_fk_mapping` 等中间结构有关（同时也会被 InMemory sink 放大；需要用“丢弃型 sink/只剖析 run 区间”进一步净化信号）。

因此需要：
1) 一套**可复现**的本地 CPU/内存 profiling 入口（不影响默认 bench/CI），
2) 一组**无语义变更**的 execution micro-opt（先把常数项压下去），并用 bench/guardrails 防止回归。

## What Changes

- Dev-only profiling：补齐 CPU profiling（py-spy）约定与入口，并沉淀可复现命令/输出目录（建议统一在 `.tmp/artifacts/perf/`）。
- Execution micro-opt（不改语义）聚焦：
  - `LoadRef` 热路径：减少 `LookupStepIr.get_from_fields()` 在 per-row loop 的重复调用与小对象分配；优化 key-normalize cache 的键结构，降低 tuple churn。
  - 字段提取：优化 `extract_field_segments` 的 Mapping 分支（减少重复 dict 查找/分支）。
  - `DenseBatchContext`：仅做局部变量提升/减少重复转换等低风险优化（不引入新语义）。
- 回归护栏：必要时新增/扩展 bench 用例或 deterministic guardrails（基于“调用次数/分配数量/是否构造中间结构”的断言，而非机器性能阈值）。

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `quality-benchmarking`: 增加 dev-only CPU profiling（py-spy）入口与稳定产物目录约定；默认 bench 仍不依赖 py-spy。

## Impact

- 受影响代码（预期）：`src/scalim/execution/context.py`、`src/scalim/execution/executor/helpers/field_access.py`、`src/scalim/execution/executor/operators/load_ref/*`
- 受影响质量资产：`tests/bench/*`（可能新增 microbench / guardrails），以及 `justfile`（可选新增 py-spy 入口）
- 风险：所有改动应保持语义不变；任何可观测行为变化（events/diagnostics 输出）都必须显式列出并有测试覆盖
