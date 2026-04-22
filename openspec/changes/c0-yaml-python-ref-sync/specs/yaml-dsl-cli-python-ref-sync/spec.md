## ADDED Requirements

### Requirement: CLI MUST provide `yaml-dsl ref-sync check-consistency` (machine-consumable, non-zero on breakage)
系统 MUST 在 `scalim-cli` 中提供一致性检查命令，用于在编辑器之外（CI / pre-commit / 脚本）检测 YAML→Python 引用破坏：

- 命令 MUST 为：`scalim-cli yaml-dsl ref-sync check-consistency <paths...>`
  - `<paths...>` MUST 支持传入一个或多个 YAML 文件/目录（目录递归扫描 `.yaml/.yml`）。
- 命令 MUST 复用共享语义实现（不得在 CLI 内复制引用解析逻辑）。
- 命令 MUST NOT 执行用户代码（仅允许文件读取与 AST 解析）。
- 当检测到任意不一致项时：
  - 进程退出码 MUST 为非 0
  - stdout MUST 输出可读摘要（linter 风格）
- 当 `--json` 指定时：
  - stdout MUST 输出可解析 JSON
  - JSON MUST 至少包含：`ok`（bool）与 `inconsistencies`（数组）

#### Scenario: broken reference fails the command
- **GIVEN** 目标路径集合中存在 YAML 引用到一个不可解析的 `symbol_key`
- **WHEN** 用户执行 `scalim-cli yaml-dsl ref-sync check-consistency <paths...>`
- **THEN** 命令 MUST 返回非 0 退出码
- **AND** 输出 MUST 包含至少一条不一致项（含 YAML 文件位置）

### Requirement: CLI MUST provide `yaml-dsl ref-sync generate` to refresh index and stubs
系统 MUST 提供一个显式的生成入口，用于刷新引用索引与引用标记工件：

- 命令 MUST 为：`scalim-cli yaml-dsl ref-sync generate <paths...>`
- 命令 MUST 生成/刷新引用索引（`<scalim_dir>/index/refs.gen.json`）与 stubs（`<scalim_dir>/stubs/**`）。
- 命令 MUST 幂等：当输入未变化时，不得产生非必要的文件改写（内容稳定）。

#### Scenario: generate creates refs.gen.json
- **WHEN** 用户执行 `scalim-cli yaml-dsl ref-sync generate <paths...>`
- **THEN** `<scalim_dir>/index/refs.gen.json` MUST 存在且为可解析 JSON

### Requirement: If an interactive fixer is provided, it MUST be confirm-before-write
若系统提供交互式修复，则其行为 MUST 满足：

- 命令 MUST 为：`scalim-cli yaml-dsl ref-sync fix-consistency --interactive <paths...>`
- 对每个不一致项，系统 MUST 展示“受影响 YAML 引用 + 建议修复”（若可推断），并在用户确认后才写回文件。
- 未确认的情况下 MUST NOT 修改任何 YAML 文件。

#### Scenario: interactive fix asks for confirmation before writing
- **GIVEN** 存在至少一个不一致项
- **WHEN** 用户执行 `... fix-consistency --interactive`
- **THEN** 系统 MUST 在写回前请求用户确认
