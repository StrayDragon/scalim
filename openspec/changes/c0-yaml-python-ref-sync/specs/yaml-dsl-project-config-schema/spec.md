## ADDED Requirements

### Requirement: scalim.yaml schema MUST validate `yaml_dsl.lsp.reference_sync`
系统 MUST 扩展 `scalim.yaml` JSON Schema 以覆盖 YAML→Python 引用同步的项目配置面：

- schema MUST 覆盖 `yaml_dsl.lsp.reference_sync` mapping，并至少包含以下字段：
  - `enabled`: boolean
  - `scalim_dir`: string（相对 `project_root` 的目录名；默认建议 `.scalim`）
  - `watch_yaml_changes`: boolean
  - `watch_python_changes`: boolean
  - `show_inconsistency_diagnostics`: boolean
  - `scan_batch_size`: integer（>= 1）
- schema-only 校验 MUST 能在类型不匹配时 fail-fast 并指向对应路径。

#### Scenario: invalid enabled type is rejected by schema-only validation
- **WHEN** 用户将 `yaml_dsl.lsp.reference_sync.enabled` 写成非 boolean（例如 string/int）
- **THEN** schema-only 校验 MUST 失败
- **AND** 错误 MUST 指向 `yaml_dsl.lsp.reference_sync.enabled`
