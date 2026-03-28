## Why

当前 `workflow` 的 IO/输出层存在三类“反直觉 + 高维护成本”的设计问题，已经成为 YAML DSL 推广与演进的主要阻碍：

- **写入语义被拆成两层且相互耦合**：demand outputs 负责“产出”；workflow `writes` 负责“再写入共享资源”。这导致同一个“输出契约”被迫分散在 demand/workflow 两个文件里，且在缺少 LSP 上下文的情况下，用户需要来回对照，错误率高。
- **pathless CSV (`container.type: csv` + `path: ""`) 是语义泄露**：它把“workflow-managed 中间态（实现细节）”暴露为 DSL 主路径，并且让 standalone demand 无法自然运行（必须依赖 workflow writes 引用才能合法），违背“单个 demand 也是一个隐式 workflow（单节点）”的直觉。
- **workbook / sheetbook 概念割裂**：用户侧两者都像“Excel book”；但 DSL 却将其建模为不同资源类型（workbooks vs sheetbooks），再叠加 CSV-only writes 约束，形成“为了实现而暴露的术语”，难以维护与扩展（例如把资源统一用于 input/output、以及让 IO 绑定更像 Dagster IOManager 的设计）。

我们希望把 IO 设计收敛到更一致的模型：**demand 定义稳定的 outputs 契约；workflow 只负责资源管理与 IO 绑定**（类似 Dagster：计算定义输出，编排只绑定 IO）。

## What Changes

- **引入统一的 `resources.books`（demand + workflow）**：
  - 使用单一资源概念 `books.<id>` 表达“Excel book”。
  - 用 `kind` 区分实现策略（例如 `xlsx_file` / `xlsx_memory`），而不再暴露 `workbooks` vs `sheetbooks` 的分裂 authoring surface。
- **demand 输出绑定下沉为“输出契约的一部分”**：
  - 新增 `outputs_defaults.to.book`，作为“多数 outputs 写到同一个 book”的简化入口。
  - 新增 `outputs[*].to`（可选覆盖），缺省 `sheet` 默认等于 `output.name`（严格校验，不做静默 normalize）。
  - 将 “append/align/header/on_mismatch” 等策略作为 book 的 `write_defaults`（并允许 per-output 覆盖），从而支持“多个 runs 同一 sheet 自动追加”的主流需求。
- **移除 `.xlsx` 输出的旧 `container` 写法（BREAKING）**：
  - 破坏性移除 `outputs[*].container.type: workbook` 作为可用 authoring surface（避免与 books 形成双路径与语义漂移）。
  - `.xlsx` 输出统一通过 `resources.books` + outputs→book 绑定表达；`{$init_var: ...}` 动态路径注入也迁移到 `resources.books.*.path` / `export_xlsx.path`。
- **workflow YAML 变薄（BREAKING）**：
  - 移除 `workflow.runs[*].writes` authoring surface；workflow 不再手写 output→sheet 映射。
  - workflow 只保留：DAG（depends_on / ctx / main_rows_from）、并发/失败策略/cache_pool、以及 `workflow.resources.books`（路径/预算/导出策略等）。
  - 编译期从 demand 的输出绑定（`outputs_defaults` + `outputs[*].to`）推导并注入等价的内部写入节点（确定性串行化与冲突策略保持可验证）。
- **彻底移除 pathless CSV hack（BREAKING）**：
  - `outputs[*].container.path: ""`（以及依赖该语义的 `workflow-managed-temp-outputs` authoring surface）不再作为 DSL 主路径存在。
  - workflow-managed 中间态仍可存在，但必须成为实现细节（自动选择内存/临时文件），并且对用户透明（不需要也不允许通过 `path: ""` 触发）。
- **更新 Python public API 的 overrides（run / run_workflow）**：
  - 增强“IO 绑定层”的 overrides：允许调用方覆盖 `resources.books.*` 的路径/预算/导出配置，以及（可选）覆盖 outputs 默认 book（IO-only）。
  - workflow 仍保持强约束：不得通过 workflow YAML 新增/删除 outputs，也不得修改 outputs 定义层（fields/aggregate/where 等），仅可做 IO 绑定与资源治理，避免引入多处改写造成隐私/发布治理复杂化。
- **同步 SSOT / docs / skills**：
  - 更新 `openspec/specs/*`（新增 capability + 修改现有 workflow/output 相关能力）。
  - 重写 `docs/doc/yaml-dsl/workflow.md` 与 `docs/doc/yaml-dsl/syntax.md` 的相关章节，删除 `writes`/pathless CSV 叙述，改为 `resources.books` + 输出绑定的单一路径。
  - 更新 `artifacts/skills/scalim-yaml-dsl`（以及相关示例）以保持与 SSOT 一致。

## Capabilities

### New Capabilities

- `yaml-dsl-books-resources`: 统一的 `resources.books`（demand/workflow）与 outputs→book/sheet 绑定语义（含默认规则与校验）。

### Modified Capabilities

- `demand-dsl`: 增加 demand 级 `resources` 与 outputs 默认绑定（并调整输出目标 authoring surface）。
- `yaml-dsl-workflow` / `yaml-dsl-workflow-validate`: workflow resources 结构与校验更新；移除 `writes` authoring surface。
- `workflow-shared-output-containers`: 共享输出容器从 `workbooks/csvs/sheetbooks + writes` 收敛为 `books + derived write nodes`。
- `workflow-managed-temp-outputs`: 移除 pathless CSV authoring surface；中间态改为内部实现细节。
- `workflow-sheetbook-resources`: sheetbook 资源对用户侧收敛为 `books.kind=xlsx_memory`；读取 rows 的内置 loader 语义随之调整。
- `yaml-dsl-output-overrides` / `output-mode-api`: Python overrides 从“replace outputs”为主，收敛到“IO 绑定层 overrides”为主（仍保留高级 escape hatch，但不作为主路径）。

## Impact

- **BREAKING（YAML authoring surface）**：`workflow.runs[*].writes`、`workflow.resources.workbooks/csvs/sheetbooks`、以及 `container.path: ""`（pathless CSV）将被移除；需要一次性升级现有 YAML（本项目默认策略：除非明确要求兼容，否则直接升级到新写法）。
- **BREAKING（.xlsx 输出写法）**：`outputs[*].container.type: workbook` 将被移除；现有 `.xlsx` 输出需要升级为 `resources.books` + outputs→book 绑定。
- **受影响代码**（非穷举）：`src/scalim/dsl/by_yaml/schema_dsl/**`、`src/scalim/dsl/by_yaml/runtime/**`、`src/scalim/dsl/by_yaml/workflow_*`、`src/scalim/workflow/**`、`src/scalim/execution/output_composition.py`。
- **受影响测试/验证**：需要新增/更新 YAML schema/validate 回归、standalone demand 输出回归、workflow 多 runs 追加写入的确定性回归，以及 Python overrides 行为回归。
- **受影响文档与技能**：`docs/doc/yaml-dsl/**` 与 `artifacts/skills/**` 需同步；涉及生成物/注入区块的部分必须通过 `just gen-docs` 刷新并由 `just qa` drift gate 校验。
