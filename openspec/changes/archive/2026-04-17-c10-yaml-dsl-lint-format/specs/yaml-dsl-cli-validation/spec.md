# yaml-dsl-cli-validation (delta) Specification

## ADDED Requirements

### Requirement: CLI MUST provide a `PROJECT_CLI_NAME yaml-dsl lint` entrypoint for YAML DSL authoring linting

系统 MUST 提供 `PROJECT_CLI_NAME yaml-dsl lint <paths...>` 命令，用于对 YAML DSL 的 authoring 风格与易踩坑点进行静态检查（不替代 `PROJECT_CLI_NAME yaml-dsl validate` 的语义校验）：

- 目标输入 MUST 支持文件与目录；目录输入时 MUST 递归发现 `.yaml/.yml` 文件
- 默认文件发现 MUST 排除 `.tmp/` 与 `dist/`（避免触碰缓存/构建产物）
- lint MUST 输出可跳转的位置（至少 `path:line`；允许 `path:line:column`），并提供稳定的规则 code（用于 CI ignore/分级）
- lint MUST 支持 `--json` 输出机器可消费的结构化 payload（包含每个 issue 的 `code/severity/message/path/range`）
- lint MUST 支持 `--fix`，且 `--fix` MUST 仅执行确定性且语义安全的修复（safe fixes only）
- exit code MUST 满足：
  - `0`: 未发现 issues
  - `1`: 发现 issues（含 `--fix` 后仍有剩余 issues 的情况）
  - `2`: 参数错误或运行时异常

v1 规则集合 MUST 至少覆盖：

- `YDL001 quoted-reference-can-be-plain`: `loader/call_by/compute/retry.should_retry` 为 quoted string，且可安全改为 plain scalar
- `YDL002 plain-scalar-looks-typed`: unquoted scalar 被 YAML 解释为 bool/null/number 等非 string，但 schema 期望 string
- `YDL004 long-call-by-suggest-block-scalar`: `call_by` 单行过长，建议改写为 block scalar 以便维护（不自动修复）

#### Scenario: `--fix` removes unnecessary quotes for safe plain scalars
- **GIVEN** 某 YAML 包含 `compute: "order_id"`
- **WHEN** 用户执行 `PROJECT_CLI_NAME yaml-dsl lint --fix demo.yaml`
- **THEN** 工具 MUST 将其修复为 `compute: order_id`
- **AND** 修复后的 YAML MUST 仍可被 YAML parser 解析为 string 值 `order_id`

#### Scenario: `--json` output contains issue codes and ranges
- **WHEN** 用户执行 `PROJECT_CLI_NAME yaml-dsl lint --json demo.yaml`
- **THEN** stdout MUST 输出可解析的 JSON
- **AND** JSON MUST 包含每条 issue 的 `code` 与 `range`（可用于 editor/CI 消费）

### Requirement: CLI MUST provide a `PROJECT_CLI_NAME yaml-dsl format` entrypoint for idempotent formatting

系统 MUST 提供 `PROJECT_CLI_NAME yaml-dsl format <paths...>` 命令，用于对 YAML DSL 执行幂等格式化（风格归一，不改变语义）：

- 目标输入 MUST 支持文件与目录；目录输入时 MUST 递归发现 `.yaml/.yml` 文件
- 默认文件发现 MUST 排除 `.tmp/` 与 `dist/`
- format MUST 幂等：对同一输入重复运行，第二次运行 MUST 产生 0 diff
- format MUST 聚焦 key 的 string value 风格归一，v1 MUST 至少覆盖：
  - `loader`
  - `call_by`
  - `compute`
  - `retry.should_retry`
- 对上述字段：当且仅当某个值被渲染为 plain scalar 后仍会被 YAML 解析为同一个 string 时，format 才 MUST 去除引号；否则 MUST 保留引号（避免 `false/null/123` 等隐式类型陷阱）
- format MUST NOT 将 block scalar（`|`/`>` 及其变体）强制折叠为单行
- format MUST 支持：
  - `--check`：仅检查是否需要改动
  - `--diff`：输出 unified diff（不写回文件）
- exit code MUST 满足：
  - `0`: 已格式化（或本就无改动）
  - `1`: `--check` 模式下存在将产生改动
  - `2`: 参数错误或运行时异常

#### Scenario: format unquotes callable references when safe and is idempotent
- **GIVEN** 某 YAML 包含 `loader: "pkg.mod:load_orders"`
- **WHEN** 用户执行 `PROJECT_CLI_NAME yaml-dsl format demo.yaml`
- **THEN** 工具 MUST 将其输出为 `loader: pkg.mod:load_orders`
- **AND** 对格式化结果再次运行 format MUST 产生 0 diff

#### Scenario: format preserves quotes for typed-looking scalars
- **GIVEN** 某 YAML 包含 `retry: {should_retry: "false"}`
- **WHEN** 用户执行 `PROJECT_CLI_NAME yaml-dsl format demo.yaml`
- **THEN** 工具 MUST 保留引号以确保该值仍为 string（不得变为 bool）

