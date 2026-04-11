# yaml-dsl-cli-validation (delta) Specification

## ADDED Requirements

### Requirement: CLI validate MUST delegate validation logic to a reusable service layer

系统 MUST 将 `PROJECT_CLI_NAME yaml-dsl validate` 的校验逻辑下沉为可复用的服务层，使 CLI 层仅负责参数解析与输出渲染：

- 校验服务层 MUST 接收结构化输入（yaml_path/schema_path/yaml_type/path_aliases/allowed_yaml_roots 等）并返回结构化 `ValidationPayload`（errors/warnings/locations/附加信息）
- CLI 层 MUST 仅做：
  - args → service 调用
  - payload → json/text renderer
  - exit code 决策
- Phase 0（迁移期）服务层化重构 MUST 保持对外输出结构与关键字段一致（或在变更中显式声明差异）

#### Scenario: service returns a payload that CLI can render without extra validation logic
- **GIVEN** 用户运行 `PROJECT_CLI_NAME yaml-dsl validate <file>`
- **WHEN** CLI 调用校验服务层
- **THEN** service MUST 返回包含 errors/warnings/locations 的结构化 payload
- **AND** CLI 渲染输出时 MUST 不需要重新实现业务校验分支

