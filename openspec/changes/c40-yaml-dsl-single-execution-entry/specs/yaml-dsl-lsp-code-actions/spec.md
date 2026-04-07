## ADDED Requirements

### Requirement: Quick Fix edits MUST write `scalim.yaml yaml_dsl.lsp` (not `yaml_dsl.editor`)
系统 MUST 将 `scalim.yaml` 中用于 LSP/discovery 的配置面固定为 `yaml_dsl.lsp.*`，并且 Quick Fix 在创建/修改 `scalim.yaml` 时 MUST 仅写入该新路径（不得再写入 `yaml_dsl.editor.*`）。

#### Scenario: addPythonRoots writes to yaml_dsl.lsp.python_roots
- **WHEN** 用户触发 Quick Fix `scalim.yaml.addPythonRoots`
- **THEN** server 应用的 edits MUST 写入 `scalim.yaml yaml_dsl.lsp.python_roots`
- **AND** MUST NOT 写入 `scalim.yaml yaml_dsl.editor.python_roots`

#### Scenario: createMinimal uses yaml_dsl.lsp keys
- **WHEN** 用户触发 Quick Fix `scalim.yaml.createMinimal`
- **THEN** 生成的 `scalim.yaml` MUST 使用 `yaml_dsl.lsp.*` 键名（不得包含 `yaml_dsl.editor.*`）

