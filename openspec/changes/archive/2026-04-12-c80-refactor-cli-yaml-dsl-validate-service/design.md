## Context

`scalim-cli yaml-dsl validate` 当前在 CLI 层承担了过多职责（参数解析、路径别名/allowed roots、schema 路径解析、YAML 类型推断、workflow validate pipeline、逐 run 校验 demand、输出渲染、退出码决策），并集中在一个 C901 函数内（`src/scalim/cli/yaml_dsl.py:_run_validate`）。

这种结构带来的问题：

- 可维护性差：新增一个参数/模式需要在复杂控制流中插入分支；
- 可测试性差：难以只测试“校验逻辑”而不同时测试 CLI I/O；
- 复用困难：若未来要在 API/服务端复用同样的校验能力，会被迫复制 CLI 逻辑。

本 refactor-0 的核心是解耦：把“校验能力”下沉为可复用的纯服务层，CLI 只负责 args → service 调用与 payload → renderer。

## Goals / Non-Goals

**Goals:**

- 提供可复用的 validation service 接口：
  - 输入：`yaml_path/schema_path/yaml_type/path_aliases/allowed_yaml_roots/...`
  - 输出：结构化 `ValidationPayload`（errors/warnings/locations/附加信息）
- CLI 层薄化：只做 args 解析、调用 service、渲染输出、返回 exit code
- Phase 0 保持对外行为一致（输出结构与关键字段尽量不变），降低回归风险

**Non-Goals:**

- 不在 Phase 0 统一/改写所有错误文案与定位口径（先搬迁逻辑，后续再治理一致性）
- 不引入新的 CLI 选项（除非是为保持兼容所必需）

## Decisions

### 1) 抽出 service 模块作为 SSOT（方案 B，Phase 0）

采用提案推荐的方案 B：

- 新增一个“纯服务层”模块：`src/scalim/dsl/yaml_dsl/validation_service.py`
- 将 `_run_validate` 中与渲染无关的校验 pipeline 迁移到 service：
  - `validate_demand_file(...) -> ValidationPayload`
  - `validate_workflow_file(...) -> WorkflowValidationResult`（包含 workflow payload + 每个 run 的 demand payload/聚合结果）
- CLI 保留 renderer 与输出结构（json/text），并保持退出码决策逻辑一致

选择 `dsl/yaml_dsl/` 域的原因（面向长期维护方向）：

- **复用语义正确**：校验能力属于 YAML DSL 领域能力，CLI 只是一个前端；未来 runtime/IDE/server 复用时不应依赖 `cli/` 包。
- **分层更清晰**：避免“非 CLI 场景 import CLI 模块”的概念污染与潜在循环依赖风险。
- **业务例子**：
  - 服务端：在 Web/API 服务中接收 YAML 文本/路径，落库前调用同一 service 做校验并返回结构化 errors/warnings（不需要 CLI renderer）。
  - IDE/LSP：在编辑器保存时调用 service 做语义校验并把 locations 映射到 diagnostics（不需要 CLI 的 argparse/输出逻辑）。

设计约束：

- service 层不得依赖 CLI 渲染细节（rich/formatting），只返回结构化结果
- service 层复用既有 `ConfigValidator`、`ErrorEnvelope`、`YamlLocationIndex` 等基础设施

### 2) Phase 0 以“搬迁但不改逻辑”为原则，Phase 1 再做一致性治理

为降低风险：

- Phase 0 不改变现有校验分支与错误聚合逻辑，只重排模块边界与函数组织
- Phase 1 再推进：
  - workflow/demand 的错误封装与 path/loc 规则一致化
  - path_aliases/allowed_yaml_roots 等策略的统一入口（避免漏传）

## Risks / Trade-offs

- **输出漂移风险**：服务层化重构容易无意改变错误顺序/字段；用快照测试（json/text）与 fixture 对拍兜底。
- **模块边界选择**：放在 `cli/` 更易搬迁但复用性差；放在 `dsl/yaml_dsl/` 复用更好但需要更谨慎的依赖整理。Phase 0 以“可复用且不引入循环依赖”为优先。

## Migration Plan

- Phase 0：
  - 引入 validation service 模块
  - 将 `_run_validate` 重构为：args → service → renderer
  - 增加典型错误场景的输出快照测试（json/text）
- Phase 1：
  - 统一错误封装与路径定位策略
  - 将 workflow validate 的每-run demand 校验管线化并显式建模（便于扩展与诊断）

## Open Questions

- 无。
