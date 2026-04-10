## Why

当前 `packages/scalim-yaml-dsl-lsp` 的语义核心（`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`）直接依赖 `scalim.dsl.yaml_dsl._internal.*`：

- 主框架内部重构会级联破坏 LSP 包（维护成本高、迭代阻塞）。
- 编辑器侧难以把 YAML DSL 当成“静态可编译语言”来做更高级的 dev features（字段上游依赖展开、执行计划可视化、路径解释等），因为很多信息目前只能通过运行时 compile/run（依赖 allowlist，且可能导入用户代码）才能得到。

我们希望把“执行前可预测”的链路（YAML 解析 / imports 展开 / schema+语义校验 / 依赖图 / ExecutionPlan 构建）收敛为主框架内的编译前端 SSOT，使：

- LSP 成为薄 adapter，几乎零成本跟随主框架演进；
- 同一套产物可复用到其它 dev 工具，并逐步替代 `frontend/scalim-viz` 的部分能力；
- 未来新增 DSL 特性时，仅需在主框架的编译前端（front-end compilation）扩展一次，避免在 LSP/server/前端多处同步实现。

## What Changes

- **BREAKING**：规划期 IR 与 ExecutionPlan 不再持有任何 Python `callable`（loader / params_builder / normalize.call_by 等），仅保留可序列化的“引用描述”（例如 Python reference 字符串与结构化解析结果）。
- 新增主框架编译前端入口（Python 3.6 兼容），将单个 YAML DSL 文档前端编译到：
  - diagnostics（对齐 validator 语义，range/path 稳定）
  - effective YAML 视图（imports/$import 展开后的只读映射/索引）
  - 静态 IR（无 callable）
  - ExecutionPlan（无 callable，可序列化）
  - 依赖图/路径追踪等辅助索引（供 LSP/viz）
- 运行时新增显式的 “runtime linking / resolution” 步骤：在 `RunOptions` allowlist 约束下把静态引用解析为可调用对象，仅在执行路径发生（不在 LSP/前端编译阶段发生）。
- `packages/scalim-yaml-dsl-lsp` 重构为薄封装：diagnostics/plan/deps 等完全委托给主框架编译前端 API；server 只保留协议、缓存与调度。

## Capabilities

### New Capabilities

- `yaml-dsl-compiler-frontend`：对单个 demand YAML，提供“编译前端产物（StaticCompilation：diagnostics/IR/plan/deps/effective view）”的 API（不导入/不执行用户代码；确定性；失败可诊断降级）。
- `yaml-dsl-plan-introspection`：提供字段依赖闭包/路径解释/执行计划序列化等查询 API，供 LSP 与可视化工具复用。
- `yaml-dsl-runtime-resolution-boundary`：定义并实现从“静态引用”到“运行期 callable”的解析边界（allowlist 约束、错误分类、可观测性）。

### Modified Capabilities

- `ir-structure`：IR 的稳定语义从“携带可执行对象”调整为“纯描述 + 运行时解析”，并明确哪些字段属于前端编译期。
- `execution-structure`：执行层获取 callable 的方式调整为从 `RuntimeBindings`/runtime registry 中获取（而非从 IR 直接取 callable），以确保 IR 可前端编译与可序列化。
- `yaml-dsl-lsp-server`：LSP 的 editor semantics SSOT 从 `packages/.../core.py` 内聚迁移到主框架编译前端 API，降低维护成本并扩展可复用能力。

## Impact

- 代码影响范围：
  - `src/scalim/spec/ir/**`、`src/scalim/planning/**`、`src/scalim/execution/**`、`src/scalim/dsl/yaml_dsl/runtime/**`：需要同步重构与适配。
  - `packages/scalim-yaml-dsl-lsp/**`：大幅瘦身与重组（主要改为调用新 API + handler 层缓存/防抖）。
- 运行时兼容性：
  - 主框架仍需 `Python 3.6` 兼容；
  - LSP package 继续 `Python >=3.10`（dev/tooling 边界）。
- 文档/生成物边界：
  - 不手改任何 `*.gen.*` 或 `BEGIN/END AUTOGEN:*` 区块。
  - 如需更新 docs/specs：以 `openspec/specs/**` 为 SSOT，按既有 `just gen-docs` / `just openspec-check` 流程刷新与校验。
- 主要风险（概述）：
  - 大范围重构存在隐蔽回归风险（尤其 execution 路径）；需要依赖接口行为测试与 notebooks 对拍兜底。
  - “静态 IR”与“运行时解析”边界划分不当会导致重复实现或性能回退，需要在 design 中收敛并建立基准测试/回归样例集。
