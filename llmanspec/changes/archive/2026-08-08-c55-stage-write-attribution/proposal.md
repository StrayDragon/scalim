---
branch: sdd/c55-stage-write-attribution
base_sha: 8982be89879228f589d050b47c1f4ad34bdb5f71
checkpointed: true
checkpoint_sha: 8982be89879228f589d050b47c1f4ad34bdb5f71
---

# 修正 write stage 归因（消除阶段误判）

## Why

`stages_total.write == 0` 而 CSV/XLSX 实际写出大量行时，用户会误判「写出很快、瓶颈在 compute/loader」。根因是：`PlanBuilder` 不再产出 `WRITE_*`/`RELEASE` 算子，真实 I/O 在 pipeline / row coordinator / `sink.close()`；`STAGE_SPAN("write")` 只在执行 WRITE_* 计划算子时累加。更糟：streaming flush 可能挂在 load/compute 计时器内，**抬高** loader/compute、进一步扭曲优化方向。

本 change 在 **不改变任何 sink 输出语义** 的前提下，把真实写出耗时正确记入 `write`（并避免双重计数）。

## What Changes

- 在 column / streaming 写出路径与（可选）`sink.close()` 上用单调时钟累加 `write` duration。
- 若 flush 发生在 load/compute 计时窗口内：从对应 stage **扣回** write 片段，或暂停外层 stage 时钟，避免双计。
- 保证 `STAGE_SPAN` / `PerformanceMetrics.stage_metrics` / 未来 `run_stats.stages_total` 对 write 可信。
- 测试：合成写出场景下 `write > 0`，且 loader+compute+write ≤ batch wall（容差内）；输出字节/行数不变。

非目标：

- 不把 WRITE_* 算子重新塞回 `PlanBuilder` 主路径。
- 不改变 book/csv 内容。

## Capabilities

### Modified Capabilities

- `performance-observability`：write stage 必须反映真实 sink 路径耗时；禁止仅依赖未规划的 WRITE_* 算子作为唯一归因。

## Impact

- **兼容**：仅观测数字变化（归因更正确）；业务输出不变。
- **风险**：计时插入点选错会导致双计或漏计 → 须有对拍测试与容差。

## Ethics

- `ethics.risk_level`: medium
- `ethics.prohibited_actions`: 为凑非零 write 而伪造数字；改变 sink I/O 顺序/内容；把 close() 耗时重复计入每个 batch 而不说明
- `ethics.required_evidence`: 合成 CSV/XLSX 场景 write>0；输出等价；stage 之和与 batch wall 关系可解释
- `ethics.refusal_contract`: 无法避免双计时不得合并进默认 bench 叙事
- `ethics.escalation_policy`: streaming 与 column 路径归因策略冲突时升级确认