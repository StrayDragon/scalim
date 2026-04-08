## ADDED Requirements

### Requirement: missing import root/alias MUST provide a Quick Fix targeting scalim.yaml

当用户在 demand YAML 中使用 imports path alias prefix（例如 `@/x.yaml` / `ALIAS:/x.yaml`）但 workspace 的 `scalim.yaml` 未配置对应 alias/import root 时,系统 MUST 提供可诊断信息与 Quick Fix,并满足:

- server MUST 提供可诊断信息（包含失败原因与建议修复点）。
- code action MUST 提供 Quick Fix，引导用户在 `scalim.yaml` 中添加缺失的 `yaml_dsl.import_roots` 条目。
- Quick Fix MUST 为 workspace-scoped，且任何文件改写 MUST 经过用户确认（WorkspaceEdit）。

#### Scenario: quick fix suggests adding import root for "@/..."
- **GIVEN** demand YAML 配置 `imports: {common: \"@/fragments/common.yaml\"}`
- **AND** `scalim.yaml` 未声明 alias `@` 的 import root
- **WHEN** LSP 生成 diagnostics 并请求 code actions
- **THEN** MUST 提供一个 Quick Fix（例如 “Add import root alias '@' to scalim.yaml”）
- **AND** 该 Quick Fix 的 edit MUST 修改 `scalim.yaml`（而不是 demand YAML）
