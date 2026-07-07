## 1. Profiling Baseline (Repro)

- [x] 1.1 固化一个可复现的 CPU profiling 入口（建议新增 `scripts/profile-execution-hotspots.py`；产物输出到 `.tmp/artifacts/perf/`）
- [x] 1.2 记录并保存 baseline 产物（cProfile/py-spy/memray）用于对比：以 `demo_big_data_report` 的 `scale=stress` / `targets=relations` / `batch_size=100` 为默认场景
- [x] 1.3 用 `memray stats`/`pstats` 汇总“Top hot functions / Top allocation sites”，写入本 change 的简短结论（可放在 design 或独立 notes）

## 2. Field Access Fastpath

- [x] 2.1 优化 `src/scalim/execution/executor/helpers/field_access.py:_extract_field_segment` 的 Mapping 分支（避免 `in` + `[]` 双查；保持语义不变）
- [x] 2.2 为该优化补一个 microbench 或在现有 bench 中加一个最小覆盖点，确保回归可见

## 3. LoadRef Hotpath Tuple Churn Reduction

说明：该 change 的主路径为 `BindingIr.mode=keys`；`rows` 模式作为二级场景（主要关注“不回归”）。

- [x] 3.1 在 `src/scalim/execution/executor/operators/load_ref/flow.py:init_first_fk_mapping` 中把 `from_field(s)` 预计算提升到 row loop 外
- [x] 3.2 重构 `src/scalim/execution/executor/operators/load_ref/context.py:LoadRefExecutionContext.normalize_key` 的缓存键结构（从 `(row_id, from_fields)` 转为两级缓存，减少 tuple 分配）
- [x] 3.3 跑 `demo_big_data_report` profiling 对比：`get_from_fields/_normalize_fields` 调用次数、`normalize_key` 分配量、以及整体耗时需有可观测下降

## 4. DenseBatchContext Micro-opts (Low Risk)

- [x] 4.1 在 `src/scalim/execution/context.py` 的 Dense path 做局部变量提升/减少重复转换（不改回退与语义契约）
- [x] 4.2 跑 `just bench`/目标场景 profile，确认 Dense path 常数项下降且无行为变化

## 5. Tooling: py-spy Integration (Dev-only)

- [x] 5.1 将 `py-spy` 纳入 dev-only 依赖（uv workspace），并确保默认 bench 不依赖它
- [x] 5.2 增加 `just profile-cpu`（py-spy record）等入口，产物写入 `.tmp/artifacts/perf/`
- [x] 5.3 同步本 change 的 delta spec：`openspec/changes/.../specs/quality-benchmarking/spec.md`

## 6. Verification & Gates

- [x] 6.1 运行 `just bench` 并保存 baseline（或 `just bench-compare` 对拍）
- [x] 6.2 运行 `just bench-memray`（或用 memray Tracker 仅包裹 run 区间）确保分配热点下降或不劣化
- [x] 6.3 运行 `just openspec-check` 确保 OpenSpec artifacts 结构与脱敏通过
- [x] 6.4 （可选）补一个最小 `rows` 模式回归点：确认 `keys` 相关 micro-opt 不会显著拖慢/放大分配（不要求优化 `rows`，只要求不退化）（由现有 `rows` 覆盖点 + `just qa` 兜底）
