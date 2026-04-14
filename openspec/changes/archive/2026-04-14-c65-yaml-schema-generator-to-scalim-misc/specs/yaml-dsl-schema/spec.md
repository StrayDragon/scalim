# yaml-dsl-schema (delta) Specification

## ADDED Requirements

### Requirement: YAML DSL JSON Schema generator MUST live in dev tooling and consume core SSOT

系统 MUST 将 YAML DSL JSON Schema 的**结构/描述 SSOT** 与**生成器实现**分层：

- 结构/描述 SSOT MUST 位于 `src/IMPL_ROOT/dsl/yaml_dsl/schema_dsl/**`（dataclass + metadata、枚举/默认值、字段描述文本等）。
- JSON Schema 的生成器实现（builder/writer/docs standardization pipeline）MUST 位于 dev tooling packages（例如 `packages/scalim-misc`）。
- 生成器 MUST 以 core SSOT 为唯一来源构建 schema，不得在 dev 包中复制字段枚举/默认值/描述文案的另一份真相。

#### Scenario: changing a field description only touches core SSOT
- **WHEN** 维护者更新某个 YAML 字段的描述性信息（例如 `markdownDescription` 文案）
- **THEN** 变更 MUST 只发生在 `src/IMPL_ROOT/dsl/yaml_dsl/schema_dsl/**`
- **AND** 重新生成 `*.gen.json` 后生成器输出 MUST 反映该变更

### Requirement: schema generation entrypoint MUST remain single and output location MUST remain stable

系统 MUST 保持 schema 生成入口与生成物位置为稳定契约：

- 唯一生成入口 MUST 为 `scripts/gen-yaml-dsl-schema.py`（由 `just gen-yaml-dsl-schema` 调用）
- 生成物 MUST 写入 `src/IMPL_ROOT/dsl/yaml_dsl/schema/{demand,workflow,scalim_yaml}.gen.json`
- 生成物为 `.gen.` 文件，MUST NOT 手工编辑（只能通过生成入口刷新）

#### Scenario: drift gate points to the single generator entrypoint
- **WHEN** `*.gen.json` 与生成器输出不一致（drift）
- **THEN** gate MUST fail-fast
- **AND** 输出 MUST 提示运行 `just gen-yaml-dsl-schema` 以修复

