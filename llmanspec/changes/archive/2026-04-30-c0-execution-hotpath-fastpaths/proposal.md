## Why

在“字段数很大、每行逻辑较薄、IO 不重”的场景里，Scalim 的耗时会被 per-row 的 Python 调度/封装成本主导（而不是业务逻辑本身），导致 compute/loader 阶段明显慢于等价的手写实现；同时我们仍希望保持 Scalim 的内存优势与开发者体验。

## What Changes

- 在不要求业务改动的前提下，为执行层热路径引入一组默认启用的 fastpaths，目标是在几乎不增加内存占用的情况下显著降低 per-row 固定开销：
  - `compute`：将当前“每次 evaluate 反复构造 globals + eval(code)”的执行模型替换为更轻量的已编译计算器调用路径（保持现有安全约束与语义）。
  - `call_by`：降低每次 call 的固定成本（参数提取、ctx 构造/拷贝、args/kwargs 组装、写回）。
  - `LoadRef`/关联写回：在不改变语义与观测事件的前提下，减少 join/分发阶段的纯 Python 循环与对象分配。
- 新增一个完全合成（无业务数据）的本地复现脚本，用于稳定重现“高字段数+薄逻辑”的热点并作为回归基线：
  - `.tmp/repro/scalim_hotpath_overhead/repro-execution-hotpath-overhead.py`（临时文件；不提交）
  - `.tmp/repro/scalim_hotpath_overhead/perf_repro_fixtures.py`（临时文件；不提交）

## Capabilities

### New Capabilities
- `execution-hotpath-fastpaths`: 执行层在保持语义与内存上界的前提下，提供默认启用的低开销执行快路径（compute/call_by/load-ref）。

### Modified Capabilities
- `execution-structure`: 允许在不改变行为的情况下对 operator hotpath 做性能重写（语义不变、事件/guardrails 行为保持）。

## Impact

- 影响范围主要在 `src/scalim/execution/**` 与 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/security.py`（compute 引擎实现）以及 YAML runtime linking 的 call_by/calculator 构建路径。
- 目标是“默认更快”，并且对内存占用增幅设硬上限（例如 <5% 或接近 0）；同时保持 Python 3.6 运行时兼容（`src/scalim/`）。
- 复现入口（无业务数据，临时文件；不要提交）：
  - `.tmp/repro/scalim_hotpath_overhead/repro-execution-hotpath-overhead.py`
  - compute 压测：`python .tmp/repro/scalim_hotpath_overhead/repro-execution-hotpath-overhead.py --case compute --rows 8000 --batch-size 4000 --compute-fields 250`
  - call_by 压测：`python .tmp/repro/scalim_hotpath_overhead/repro-execution-hotpath-overhead.py --case call_by --rows 20000 --batch-size 20000 --callby-fields 60`
  - load_ref 压测：`python .tmp/repro/scalim_hotpath_overhead/repro-execution-hotpath-overhead.py --case load_ref --rows 20000 --batch-size 20000 --ref-fields 30`
