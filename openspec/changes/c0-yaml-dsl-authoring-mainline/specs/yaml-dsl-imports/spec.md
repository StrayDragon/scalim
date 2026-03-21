## MODIFIED Requirements

### Requirement: imports path MUST support relative fragments (v2) without relying on git repo root
系统 MUST 放宽 `imports.<alias>` 的路径规则，使其在 v2 支持相对路径 fragments，并且不依赖 git repo root 推断。

当解析 demand YAML 时（包含被导入的 fragments）：

- imports 路径解析基准 MUST 为**当前 YAML 文件**所在目录（确定性）
- imports MUST 支持以下相对文件路径形态（`.yaml/.yml`）：
  - `./x.yaml`、`x.yaml`
  - `x/y.yaml`（子目录）
  - `../x.yaml`（父目录）

同时，系统 MUST 拒绝以下路径：

- 绝对路径（含 Windows 盘符/UNC）
- 任意 URI scheme（形如 `*://...`，包括 `file://`、`http(s)://`、`scalim://`）
- 预留的 alias 前缀/语法（例如 `@/x.yaml`、`COMMON:/x.yaml`）

#### Scenario: imports can reference a sibling fragment
- **GIVEN** demand YAML 位于 `./reports/demand.yaml`
- **AND** fragment 文件位于 `./reports/common.yaml`
- **WHEN** demand YAML 配置 `imports.common: ./common.yaml`
- **THEN** imports MUST 成功解析并加载该 fragment

#### Scenario: imports can reference a fragment in a child directory
- **GIVEN** demand YAML 位于 `./reports/demand.yaml`
- **AND** fragment 文件位于 `./reports/_shared/common.yaml`
- **WHEN** demand YAML 配置 `imports.shared: ./_shared/common.yaml`
- **THEN** imports MUST 成功解析并加载该 fragment

#### Scenario: imports can reference a fragment in a parent directory
- **GIVEN** demand YAML 位于 `./reports/demand.yaml`
- **AND** fragment 文件位于 `./_shared/common.yaml`
- **WHEN** demand YAML 配置 `imports.shared: ../_shared/common.yaml`
- **THEN** imports MUST 成功解析并加载该 fragment

#### Scenario: absolute paths and URI schemes are rejected
- **WHEN** `imports.common` 为 `/etc/passwd`、`C:\\secrets.yaml`、`file:///tmp/x.yaml`、`scalim://yaml-dsl/presets/common.yaml` 或 `@/fragments/common.yaml`
- **THEN** 校验 MUST 失败并提示仅支持相对文件路径（`.yaml/.yml`）
