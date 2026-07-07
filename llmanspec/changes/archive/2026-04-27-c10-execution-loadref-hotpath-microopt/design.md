## Context

用户侧确认：
- `viz` 不在生产常用路径（仅开发偶尔用或不用）
- YAML 解析/导入（双解析、imports cache）不是主要瓶颈
- `LoadRef` 绑定模式以 `keys` 为主；`rows` 模式存在但较少使用（且更难在业务侧落地）

因此本 change 仅聚焦 **execution 热路径** 的常数项优化与 profiling 工具链完善。

## Profiling Method (SSOT)

本 change 的 profiling 以仓库自带自生成用例为 SSOT（避免引入外部数据/依赖）：

- 用例：`packages/scalim-misc/src/scalim_misc/demo_big_data_report/*`
- 规模：`scale=stress`（10k orders）
- 目标字段：`targets=relations`（覆盖 `LoadRef` 链路）
- 批大小：`batch_size=100`

备注：`demo_big_data_report` 的 `BindingIr` 默认 `mode="keys"`，因此该基准剖析代表主路径（`keys`）。`rows` 模式相关剖析仅作为二级补充/回归护栏。

建议在本地生成/查看剖析产物：
- cProfile：`.tmp/artifacts/perf/ecommerce_relations_stress.prof`
- py-spy flamegraph：`.tmp/artifacts/perf/ecommerce_relations_stress_pyspy.svg`
- memray：`.tmp/artifacts/perf/ecommerce_relations_stress.bin`（注意：若从进程启动开始跟踪，会包含 import-time 噪声；更推荐“只包裹 run 区间”的 Tracker 方式）

复现命令（参考）：
- `python -m cProfile -o .tmp/artifacts/perf/ecommerce_relations_stress.prof <profile_script> ...`
- `py-spy record -o .tmp/artifacts/perf/ecommerce_relations_stress_pyspy.svg -- <python> <profile_script> ...`
- `memray run -o .tmp/artifacts/perf/ecommerce_relations_stress.bin <profile_script> ...`

## Findings Summary (CPU)

在上述配置下，cProfile 显示主要 CPU 消耗集中在：
- `src/scalim/execution/context.py`（Dense path）：`_idx_of` / `set_field_value` / `get_field_value`
- `src/scalim/execution/executor/operators/load_ref/flow.py`：`write_final_step` / `_write_ref_fields` / `_resolve_ref_field_value`
- `src/scalim/execution/executor/helpers/field_access.py`：`extract_field_segments` / `_extract_field_segment`
- `src/scalim/execution/executor/operators/load_ref/context.py`：`normalize_key`

这些函数都是“每行/每字段/每 step”级别被重复调用的常数项，优化空间来自：
- 减少重复分支与重复对象构造（尤其 tuple churn）
- 减少 dict 二次查找与 attribute lookup
- 把“每行计算一次”的逻辑提升到“每 step / 每批次一次”

## Findings Summary (Memory)

memray（全进程跟踪）显示 `LoadRef` 路径会产生大量小对象分配：
- `normalize_key`（key_normalize_cache）与 `init_first_fk_mapping` 的中间映射结构
- 以及 InMemory sink 的列对齐写入（这属于测试 sink 行为，真实 sink 可能不同；需要剥离/对齐）

结论：需要优先减少 `LoadRef` 热路径中的“每行创建 tuple key/临时容器”。

## Profiling Snapshot (Repro + Before/After)

复现入口（SSOT）：
- time-only：`uv run python scripts/profile-execution-hotspots.py --scale stress --targets relations --batch-size 100`
- cProfile：`uv run python scripts/profile-execution-hotspots.py --profile cprofile --scale stress --targets relations --batch-size 100`
- memray（含小对象）：`uv run python scripts/profile-execution-hotspots.py --profile memray --scale stress --targets relations --batch-size 100`
- py-spy flamegraph：`just profile-cpu`（写入 `.tmp/artifacts/perf/ecommerce_relations_stress_pyspy.svg`）

baseline 产物目录：`.tmp/artifacts/perf/`

对比结果（scale=stress, targets=relations, batch_size=100）：
- time-only（仅包裹 run 区间）：`0.809673s` → `0.756587s`（约 `-6.6%`）
- cProfile 调用次数：
  - `LookupStepIr.get_from_fields/_normalize_fields`：`205,500` → `6,600`
  - `LoadRefExecutionContext.normalize_key`：`110,000`（不变，但 `cumtime 0.274s → 0.216s`）
- memray（`trace_python_allocators=true`）：
  - `_normalize_fields` 分配量显著下降（不再进入 top 列表；扩大到 `-n 2000` 后仅剩极少量）

## Design: Planned Changes

### 1) `extract_field_segments` Mapping fastpath

目标：在常见 `data` 为 `dict` 且 `segments` 很短（尤其长度=1）的场景，减少每次字段提取的 dict 查找与分支。

候选改动：
- `src/scalim/execution/executor/helpers/field_access.py:_extract_field_segment`
  - Mapping 分支从 `if segment in mapping: return mapping[segment]` 改为 `return mapping.get(segment)`
  - 语义保持不变（缺失与值为 `None` 仍返回 `None`）

### 2) `LoadRef` from_fields 预计算（减少 tuple churn）

目标：避免在 per-row loop 中反复调用 `LookupStepIr.get_from_fields()`（会构造新 tuple），并避免把 `(row_id, from_fields)` 作为 dict key 造成大量 tuple 分配。

候选改动（不改变外部语义）：
- `src/scalim/execution/executor/operators/load_ref/flow.py:init_first_fk_mapping`
  - 在进入 row loop 前预计算单字段 `from_field = first_step.get_from_fields()[0]`
  - multi-field 分支预计算 `from_fields = first_step.get_from_fields()` 并复用
- `src/scalim/execution/executor/operators/load_ref/context.py:LoadRefExecutionContext.normalize_key`
  - 将 cache 结构从 `Dict[(row_id, from_fields), value]` 调整为两级：
    - `Dict[from_fields, Dict[row_id, value]]`（`from_fields` 在同一步内稳定，数量小）
  - 调用侧在每个 step/分支内传入或复用已计算的 `from_fields`

验收：memray/cProfile 中 `get_from_fields/_normalize_fields` 的调用次数与 `normalize_key` 分配量显著下降，且执行语义不变。

### 3) `DenseBatchContext` 局部 micro-opt（低风险）

目标：压缩 Dense path 的常数项开销（大量 `_idx_of`/`set_field_value` 调用）。

候选改动：
- 局部变量提升：避免重复 `int(...)` 与重复属性读取
- 保持“条件不满足回退/报错”的契约不变（见 `openspec/specs/execution-dense-batch/spec.md`）

### 4) Dev-only CPU profiling integration (py-spy)

目标：补齐与 memray 对称的 CPU profiling 入口，默认不影响 bench/CI。

候选改动：
- 将 `py-spy` 作为 dev-only 依赖（uv workspace / dev extras）
- 在 `justfile` 中提供 `profile-cpu` / `profile-cpu-top` 等入口（输出到 `.tmp/artifacts/perf/`）
- 文档/规范更新见本 change 的 specs delta（`quality-benchmarking`）

## Guardrails & Verification

- 性能趋势：`just bench` / `just bench-compare`
- 内存趋势：`just bench-memray`（已有）
- 关键热路径（LoadRef wants-gated）回归：现有 `tests/bench/test_bench_loadref_wants_gated.py` +（可选）新增 deterministic 断言，避免在“unwanted”路径引入逐行循环/额外结构构造
- `rows` 模式回归：由于主路径为 `keys`，`rows` 的目标是“不退化”（必要时补一个最小覆盖点/小规模场景，避免误伤）
