## MODIFIED Requirements

### Requirement: imports path MUST allow cross-subdirectory fragments (v2) while preserving safety boundaries
系统 MUST 放宽 `imports.<alias>` 的路径规则，使其允许相对路径包含子目录（v2）。

当解析 demand YAML 时：

- imports 路径解析基准 MUST 仍为 demand YAML 文件所在目录
- imports MUST 允许相对路径包含子目录（例如 `./_shared/sources.yaml`、`_shared/sources.yaml`）

同时，系统 MUST 继续拒绝以下路径（保持治理与安全边界）：

- 绝对路径（含 Windows 盘符/UNC）
- 包含 `..` 的父目录逃逸
- `@`/`:` 等 alias/URI 语法

#### Scenario: imports can reference a fragment in a child directory
- **GIVEN** demand YAML 位于 `./demand.yaml`
- **AND** fragments 文件位于 `./_shared/sources.yaml`
- **WHEN** demand YAML 配置 `imports.shared: ./_shared/sources.yaml`
- **THEN** imports MUST 成功解析并加载该 fragment
