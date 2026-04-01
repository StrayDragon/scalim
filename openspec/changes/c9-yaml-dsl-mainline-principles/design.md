## Context

当前 YAML DSL 收敛讨论里,有一些内容适合拆成独立 change,例如:

- workflow schema/runtime drift
- `observability.*` 的迁出
- `guardrails` / `retry` 的 runtime policy 边界
- `write_defaults` / `outputs[*].write`
- demand imports scope

但也有一批内容是跨所有专题共享的:

- 我们不要 `dsl_version`
- 我们不要并行版本解析器
- YAML 应聚焦 authoring surface
- runtime policy 应尽量收口到 Python / CLI
- workflow 不应成为 imports expansion 的新战场

这些内容如果不单独沉淀,后续每个子提案都得重复解释一次,而且最终很容易出现原则丢失。

## Goals

- 明确 YAML DSL 主线收敛的上位原则
- 给拆分后的 change 提供优先级与依赖顺序
- 让后续专题提案可以建立在统一原则之上

## Non-Goals

- 不决定每个专题的最终实现细节
- 不要求在这个 change 中产出全部 specs/tasks

## Mainline Principles

### 1. 单主线演进,不引入 `dsl_version`

主线 DSL 应原地演进:

- 不引入 `dsl_version`
- 不通过 CLI/schema/modeline 选择并行版本
- 不维护多套 parser/validator/schema artifact

旧写法通过升级工具、lint、迁移提示处理,而不是通过长期并行版本解析器兜底。

### 2. `YAML = authoring`, `Python/CLI = runtime policy`

YAML 主线应聚焦:

- sources / fields / relations / outputs
- 少量可移植的资源声明

而以下内容默认视为 runtime policy 候选:

- observability
- guardrails
- retry
- batch_size
- diagnostics / staging / environment-sensitive knobs

### 3. KV-first

凡是需要稳定 ID、引用、复用的结构,优先 mapping:

- `sources`
- `fields`
- `relations`
- `resources`

只有顺序语义不可替代时,才使用 list:

- `outputs`
- `workflow.runs`
- `relation.steps`

### 4. 维护成本与可读性优先于保留低频边缘旋钮

当出现取舍时,主线默认优先:

- 更少的入口
- 更清晰的分层
- 更低的 schema/runtime/docs 漂移成本

而不是为了兼容低频、重叠或边缘配置继续扩大主线表面积。

### 5. workflow 保持小而声明式

workflow 应聚焦:

- `runs`
- `depends_on`
- `init_vars`
- 少量稳定的 orchestration/runtime knobs

而 diagnostics、staging、等待策略等环境敏感项,默认应向 Python / CLI 收口。

### 6. workflow 不扩张 imports expansion

workflow 的职责是 orchestration,不是片段组合系统。

因此 workflow 不应为了对齐 demand 而补 imports expansion。相关 drift 应优先通过收紧 schema/runtime 契约解决。

## Split Plan

### Stage 1: 基础可信度

- `c10-yaml-dsl-schema-workflow-alignment`

### Stage 2: 方向明确的独立专题

- `c12-yaml-dsl-observability-out-of-yaml`

### Stage 3: 边界型专题

- `c13-yaml-dsl-runtime-policy-boundary`
- `c14-yaml-dsl-write-policy-and-output-extras`
- `c15-yaml-dsl-demand-imports-scope`

### Stage 4: 编辑器/LSP 侧补充

- `c999-yaml-dsl-lsp`
  - 负责 editor semantics 边界
  - 这些接口可以是“内部导出但稳定可依赖”的特例,不必上升为面向普通用户的 public API 承诺

## Notes On Editor Semantics

关于 editor semantics 的部分,现决定调整为:

- 这部分不再单独作为 `c11` change
- 相关能力由 `c999-yaml-dsl-lsp` 继续承接
- 在 `scalim` 主包中可以采用“尽量隐藏的内部导出”策略,作为 editor/tooling 的特例接口
- 未来实现形态可以是:
  - `packages/` 下的独立 LSP server（例如 Python 3.10）
  - VSCode extension 调用主包
  - 之后再评估 Pyodide / WASM 等形态

## Current Assessment

- 当前拆分顺序满足“先定基础,再定边界,最后补 editor/tooling”的节奏
- 基于对原始大提案的回扫,目前未发现仍然悬空的主线总原则

仍需继续跟进的,主要不是新的“总原则缺口”,而是后续具体专题里的执行型归属,例如:

- migration tooling 最终落在哪个专题
- docs / notebooks / skills 的改造如何分批跟随专题推进
- 若后续发现 `main_source` vs `sources` 需要单独结构性重构,可能再补一个更具体的专题 change
