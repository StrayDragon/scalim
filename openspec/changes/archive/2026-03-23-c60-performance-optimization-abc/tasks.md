## 1. c0 基线与护栏（防回归优先）

- [ ] 1.1 (c0) 确认并记录基线：`just quick-check-only-py` 可作为日常基线运行（保持在本变更实施过程中不退化）。
- [ ] 1.2 (c0) 为 wants-gated 热路径新增确定性单测护栏：覆盖 `LoadRefOperatorExecutor` 的 `relation_lookup` 在未订阅时不得引入 `O(row_count)` 诊断开销（调用点不应遍历 `current_mapping.items()` 做 hit/miss 分类；对应 `src/scalim/execution/executor/operators/load_ref/executor.py` + `specs/hooks-observability-structure/spec.md`）。
- [ ] 1.3 (c0) 新增/补齐最小可运行的 micro-bench 场景：覆盖 `LoadRef` 热路径（无观测/有观测）并输出 JSON 结果用于对比（对应 `specs/perf-regression-guardrails/spec.md`）。
- [ ] 1.4 (c0) 明确并固化 memray 采集与产物目录：确保 `just bench-memray*` 输出到 `.benchmarks/memray/` 且不影响默认 bench（对应 `specs/perf-regression-guardrails/spec.md`）。
- [ ] 1.5 (c0) 为本变更建立验收口径：至少包含 `just quick-check-only-py`、`just bench-compare-fail`（本地基线）与 1 次 memray 对比记录。
  - 备注：不新增/修改 CI perf job；CI 配置保持不变（以 `just qa` 链路为主）。

## 2. A：Hotpath wants-gated + 减少无效分配

- [ ] 2.1 (c0) 在 `LoadRef` 关联诊断路径引入调用点 wants-gate：未订阅 `relation_lookup` 时跳过逐行 hit/miss 分类（`fk_value in intermediate_result` membership check）与 `fk_type` 等辅助字段构造（对应 `src/scalim/execution/executor/operators/load_ref/executor.py` + `specs/hooks-observability-structure/spec.md`）。
- [ ] 2.2 (c1) 审计并修复其它“未订阅仍做规模线性工作”的热路径（优先 execution/ob/hub 周边），并为每个点补充单测或 micro-bench。
- [ ] 2.3 (c1) 基准验证：对 `tests/bench` 相关 group 做 before/after 记录，确保趋势向好且无语义回归。

## 3. B：DenseBatchContext（降低 BatchContext 对象/哈希开销）

- [ ] 3.1 (c1) 定义 Dense path 的启用条件与回退策略，并补齐等价性测试（对应 `specs/dense-batch-context/spec.md`）。
- [ ] 3.2 (c1) 实现 DenseBatchContext 并接入 pipeline/batch executor（包含行级释放/字段释放语义）。
- [ ] 3.3 (c1) 适配 `OverlayBatchContext`/adaptive 相关路径，确保 overlay 语义不变（对应 `specs/dense-batch-context/spec.md`）。
- [ ] 3.4 (c1) 基准与 memray 对比：在目标场景记录 RSS 峰值与吞吐变化，沉淀结论到变更说明。

## 4. C：sink aligned-write fastpath（减少写出阶段中间 dict）

- [ ] 4.1 (c1) 在 sink 接口中引入可选 aligned-write fastpath 方法（保持现有接口可用）（对应 `specs/sink-fastpath/spec.md`、`specs/sinks-contracts/spec.md`）。
- [ ] 4.2 (c1) pipeline 优先使用 fastpath：列式写出与行式流式写出均需覆盖，并确保不再构造等价中间 dict（对应 `specs/sink-fastpath/spec.md`）。
- [ ] 4.3 (c1) 内建 sinks 覆盖 fastpath：至少覆盖内存 sink 与文件 sink（如 CSV），并补齐“fastpath 与旧路径输出一致”的测试（对应 `specs/sinks-contracts/spec.md`）。
- [ ] 4.4 (c2) 基准与内存对比：验证宽表/大批次写出阶段的分配峰值下降，且吞吐不回退。

## 5. 文档与治理（如触及 docs/site）

- [ ] 5.1 (c1) 若需要更新文档：仅修改 SSOT（非 `.gen.` 文件、非 `BEGIN/END AUTOGEN` 区块内部），并通过 `just gen-docs` 生成站点受控产物。
- [ ] 5.2 (c1) 验收：`just docs-drift-check`、`just doc-governance-check` 通过；OpenSpec 工件通过 `just openspec-check`。

## 6. 后置提案（仅 proposal.md）

- [ ] 6.1 在 A/B/C 全部完成并稳定后，创建后置 change `c700-*`（仅 `proposal.md`）：讨论更抽象的 fastpath 载荷协议（例如 MappingView/SequenceView）与更激进的 perf 工作流，但不在本变更实现与验收范围内。
