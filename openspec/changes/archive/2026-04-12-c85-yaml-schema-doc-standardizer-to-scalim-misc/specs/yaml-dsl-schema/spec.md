# yaml-dsl-schema (delta) Specification

## ADDED Requirements

### Requirement: schema docs standardization MUST be provided via an optional dev plugin without impacting runtime users

YAML DSL schema 生成管线 MAY 包含“schema docs 标准化”阶段（例如生成/补全 `markdownDescription`、提取示例片段、校验枚举语义一致性），但该能力 MUST 以 dev-only 插件形式提供，避免将 gen-only 复杂度强绑定到主包运行时：

- 主包 MUST 提供一个 ImportError-safe 的标准化 hook（例如 `maybe_standardize_schema_docs(schema) -> schema`）
- 当 dev 插件（例如 `scalim-misc`）不存在时：
  - hook MUST no-op
  - 主包 import 与 runtime MUST 正常工作（不得因缺少 dev 包而失败）
- 在 dev/CI 的 schema 生成环境中，生成入口 SHOULD 确保 dev 插件可用；若不可用：
  - CI 环境 MUST fail-fast（非零退出码）
  - 本地开发环境 SHOULD 输出明确 warning 并提示“生成结果将降级”（并给出安装插件的修复建议）

#### Scenario: missing dev plugin does not break runtime imports
- **GIVEN** 用户环境未安装 `scalim-misc`
- **WHEN** 用户仅使用 runtime 能力（compile/validate/run/workflow）或 import 主包
- **THEN** import 与运行 MUST 成功
- **AND** schema docs 标准化 hook MUST 自动 no-op

#### Scenario: schema generation uses standardizer when available
- **GIVEN** dev/CI 环境安装了 `scalim-misc`
- **WHEN** 执行 `just gen-yaml-dsl-schema`（或等价生成入口）
- **THEN** 生成器 MUST 通过可选 hook 应用 schema docs 标准化
- **AND** 生成结果 MUST 满足 `yaml-dsl-schema` 中对 `markdownDescription`/示例的要求
