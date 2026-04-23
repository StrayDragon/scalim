## ADDED Requirements

### Requirement: executeCommand MUST support `scalim.dumpDemandSnapshots` (demand-only static snapshots)
系统 MUST 通过 `workspace/executeCommand` 暴露一个 demand-only 的静态快照导出命令：

- command id MUST 为 `scalim.dumpDemandSnapshots`
- arguments MUST 至少包含一个 document URI（作为快照导出的入口）
- 成功时 MUST 返回 `execution_plan/v1` 与 `execution_deps/v1` 快照（JSON 可序列化）
- 失败时 MUST 返回可诊断的错误结构（不得 crash / 退出）
- 返回值 MUST NOT 回显 demand YAML 正文（避免把用户文档作为数据通道）

#### Scenario: dumpDemandSnapshots returns plan/deps snapshots for a valid demand YAML
- **GIVEN** client 提供一个 demand YAML 文档 URI
- **AND** diagnostics 通过（无 errors）
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.dumpDemandSnapshots`
- **THEN** server MUST 返回 `ok=true`
- **AND** MUST 包含 `plan_snapshot`（`execution_plan/v1`）与 `deps_snapshot`（`execution_deps/v1`）

#### Scenario: dumpDemandSnapshots rejects non-demand YAML with explain_only
- **GIVEN** client 提供一个非 demand 的 YAML 文档 URI（例如 workflow YAML）
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.dumpDemandSnapshots`
- **THEN** server MUST 返回 `ok=false`
- **AND** `kind` MUST 为 `explain_only`
- **AND** message MUST 明确说明仅支持 demand YAML

#### Scenario: dumpDemandSnapshots returns diagnostics_failed when diagnostics has errors
- **GIVEN** client 提供一个 demand YAML 文档 URI
- **AND** 该文档存在 YAML DSL diagnostics errors
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.dumpDemandSnapshots`
- **THEN** server MUST 返回 `ok=false`
- **AND** `kind` MUST 为 `diagnostics_failed`
- **AND** MUST 包含可读的 `errors`（与 warnings 可选）

### Requirement: executeCommand MUST support `scalim.dumpDemandLens` (sidebar lens payload)
系统 MUST 通过 `workspace/executeCommand` 暴露一个面向 VSCode “边栏透镜(Demand)” 的聚合导出命令：

- command id MUST 为 `scalim.dumpDemandLens`
- arguments MUST 至少包含一个 document URI
- command MAY 接收一个可 JSON 序列化的 options 参数（作为第二个 argument），用于指定 focus（例如 `focus_output_index`）
- 成功时 MUST 返回一屏渲染所需的最小 payload（outputs 列表 + Mermaid + 节点锚点）
- 失败时 MUST 返回可诊断的错误结构（不得 crash / 退出）

成功 payload MUST 至少包含：

- `outputs`: outputs 列表（顺序与 YAML 保持一致）
  - 每个 item MUST 至少包含 `output_index` 与 `name`
  - 每个 item MUST 提供“定位”所需的声明位置（例如 `file_path` + `range` 指向 `outputs[*].name`）
- `focus_output_index`: 当前 focus output 的 index（由 options 或默认策略决定）
- `mermaid_text`: 当前 focus 对应的 Mermaid 文本（`flowchart`）
  - Mermaid MUST 表达 “字段依赖 DAG”
  - Mermaid MUST 按 `source_id` 分组（subgraph），以提升可解释性
- `node_anchors`: Mermaid node → 字段定义位置的锚点映射，用于点击跳转
  - 目标位置 MUST 指向字段定义处（源字段/派生字段），而不是 outputs 引用处
  - 当字段定义不可定位时，server MUST 允许该 node 缺失锚点（不得 crash）

#### Scenario: dumpDemandLens returns outputs and mermaid for a demand YAML
- **GIVEN** client 提供一个 demand YAML 文档 URI
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.dumpDemandLens`
- **THEN** server MUST 返回 `ok=true`
- **AND** MUST 包含非空 `outputs`
- **AND** MUST 包含 `mermaid_text` 与 `node_anchors`

#### Scenario: dumpDemandLens rejects non-demand YAML with explain_only
- **GIVEN** client 提供一个非 demand 的 YAML 文档 URI
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.dumpDemandLens`
- **THEN** server MUST 返回 `ok=false`
- **AND** `kind` MUST 为 `explain_only`
- **AND** message MUST 明确说明仅支持 demand YAML

### Requirement: legacy command id `scalim.dumpPlanDeps` MUST be removed (breaking rename)
系统 MUST 将原命令 `scalim.dumpPlanDeps` 视为已移除：

- LSP server MUST NOT 再注册 `scalim.dumpPlanDeps`
- client MUST 迁移为调用 `scalim.dumpDemandSnapshots`

#### Scenario: dumpPlanDeps is no longer available via executeCommand
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.dumpPlanDeps`
- **THEN** server MUST 返回“未知命令/不可用”的失败（例如 JSON-RPC error 或等价结果）
- **AND** MUST NOT 返回任何 plan/deps 快照 payload
