## Context

workflow 相关模块目前呈现“单文件聚合多职责 + 巨型函数 + 复杂度豁免”的维护信号：

- `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`（1600+ 行；`run_workflow` 复杂度豁免）
- `src/scalim/dsl/by_yaml/runtime/workflow_resources.py`（资源创建/写入/提交/事件/导出等职责混杂）
- `src/scalim/dsl/by_yaml/workflow.py`（workflow YAML 的解析、路径解析、校验等也在同一文件叠加）
- `src/scalim/cli/yaml_dsl.py`（workflow validate/路径解析等 CLI glue 分支增多）

这种结构会放大改动半径与回归风险，且让“边界治理”（runtime ↔ execution ↔ ob/hooks）越来越难维持。

约束：

- `src/scalim/` 运行时需兼容 Python 3.6；by_yaml 内优先相对导入，避免引入新的循环依赖。
- 本变更为重构：对外语义与稳定入口必须保持不变（spec 要求 `run_workflow` 等稳定入口仍可导入/调用）。
- 可假设其它依赖性 change 已完成（例如 deadlock hardening、cache pool 语义收敛等），本变更只聚焦“模块与职责拆分 + 护栏”。

## Goals / Non-Goals

**Goals:**

- 将 workflow runtime 按职责拆分为更小的内部模块（config/load/compile/execute/report/resources 等），并降低单文件复杂度。
- 保持稳定入口不变：
  - 调用方继续从既有路径导入 `run_workflow`（以及既有 validate/compile 入口，如果存在）
  - 内部实现可移动/拆分，但对外 import path 不应要求调用方修改
- 让关键 phase 变成可单测的纯函数/小类，提高可维护性与可回归性（尤其是并发/失败策略/资源写入顺序）。

**Non-Goals:**

- 不新增 workflow runner CLI（仍以 Python 入口为主；CLI 仅做 validate/glue 的必要调整）。
- 不修改 workflow authoring surface（YAML schema/语义规则不变）。
- 不在本变更内做大规模性能优化（只做结构拆分；性能优化另有 change）。

## Decisions

### 1) 模块组织：保留稳定入口文件，新增内部子模块承载职责

**决策：**

- 保留 `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py` 作为稳定入口（thin wrapper），将实现拆到同目录的新内部模块中（避免“文件 → 包”重命名带来的 import 破坏）：
  - `workflow_load.py`：加载/预处理 workflow YAML（含 template_vars 预编译）、解析 config、路径解析（委托到 workflow 配置模块）
  - `workflow_compile.py`：将 workflow config 编译为 workflow IR（DAG、options、resources slots 等）
  - `workflow_execute.py`：调度执行（并发、failure_policy、cache_pool 生命周期、ctx store）
  - `workflow_report.py`：结果汇总、诊断输出（面向调用方的返回结构与可观测性桥接）
- `workflow_resources.py` 拆分为资源类型子模块（同目录）：
  - `workflow_resources_base.py`：资源 registry / 生命周期接口 / 统一的事件发射边界
  - `workflow_resources_sheetbook.py`、`workflow_resources_workbook.py`、`workflow_resources_csv.py`：各资源的具体实现

**备选：**

- 直接把 `workflow_entrypoints.py` 改为 package：会破坏现有 import 路径（或需要大量 re-export 兼容层），风险与迁移成本较高。

### 2) workflow 配置模块拆分：把“路径解析/validate/加载”与 runtime 执行解耦

**决策：**

- 将 `src/scalim/dsl/by_yaml/workflow.py` 中的职责拆分为：
  - `workflow_config.py`：纯配置解析与语义校验（mapping/text → dataclass config）
  - `workflow_paths.py`：路径解析（`runs[*].demand` / path_aliases），并与 allow-roots 等安全策略对齐（若对应 change 已完成，则此处仅复用其 helper）
  - `workflow_types.py`（可选）：放置 dataclass/异常类型，降低互相 import 的耦合
- CLI `yaml_dsl.py` 仅调用新的 `workflow_paths` / `workflow_config`（减少 CLI 与 runtime 的耦合）。

### 3) `run_workflow` 的 phase 拆分：把巨型函数拆成可测试边界

**决策：**

将 `run_workflow(...)` 拆成显式 phase 函数（每个函数尽量纯、入参/出参明确）：

1. `_load_workflow_config(...)`：读取 workflow YAML →（可选）模板预编译 → parse/validate config
2. `_compile_workflow_ir(...)`：config → workflow IR（含 DAG、options、resources slots、writes intents）
3. `_execute_workflow_ir(...)`：调度执行 demand nodes + write nodes（并发/失败策略/cancel 策略）
4. `_finalize_workflow_result(...)`：聚合 outcomes、resources commit/discard、生成最终返回结构

并将“复杂度豁免”逐步收敛到极少数 glue 层（理想状态：仅 wrapper 层保留，核心 phase 无需豁免）。

### 4) 护栏：稳定入口 smoke + 关键不变量单测

**决策：**

- 增加稳定入口 smoke test：确保 `from scalim.dsl.by_yaml import run_workflow` / `from scalim.dsl.by_yaml.runtime.workflow_entrypoints import run_workflow` 仍可导入并执行最小 workflow。
- 增加关键不变量单测（优先级从高到低）：
  - failure_policy（all_fail / primary_only）的取消/禁用语义
  - writes 顺序确定性（按 runs 顺序 + writes 顺序）
  - cache_pool acquire/release/evict 的归因字段与生命周期边界
  - ctx store 的可见性边界（仅依赖闭包可读）

## Risks / Trade-offs

- [回归风险] 大量移动/拆分容易引入 import 错误或遗漏行为 → 缓解：拆分按 phase 小步提交；每步都跑 `just qa`；并用稳定入口 smoke test 兜底。
- [循环依赖] runtime/workflow 与 execution/ob/hooks 的边界更复杂 → 缓解：内部模块按依赖方向分层（config/paths 最底层；execute 最上层），并严格避免反向 import。
- [测试维护] 新增不变量测试需要补齐更多 fixtures → 缓解：优先覆盖最关键语义；其它细节用集成测或后续增量补齐。

## Migration Plan

1. 先落地稳定入口 smoke test 与关键不变量测试（作为重构护栏）。
2. 引入内部子模块骨架，把 `run_workflow` 拆成 phase 函数，但先在同文件内拆小（减少一次性移动风险）。
3. 逐步把 phase 实现迁移到新模块（每次迁移后保持 public API 不变）。
4. 拆分 `workflow_resources.py` 与 `workflow.py` 的职责密度，确保 CLI glue 依赖更浅。
5. 运行 `just openspec-check` 与 `just qa` 作为最终门禁。
