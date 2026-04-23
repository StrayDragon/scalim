## ADDED Requirements

### Requirement: executeCommand MUST support `scalim.dumpYamlPythonReferences` (document-scoped refs)
系统 MUST 通过 `workspace/executeCommand` 暴露一个用于查询“当前 YAML 文档内的 YAML→Python 引用”的命令：

- command id MUST 为 `scalim.dumpYamlPythonReferences`
- arguments MUST 至少包含一个 document URI（作为引用查询入口）
- 成功时 MUST 返回 JSON 可序列化 payload，且 MUST 至少包含：
  - `ok`（bool）
  - `references`（数组）
- 每个 reference item MUST 至少包含：
  - `symbol_key`（`module:attr`）
  - `yaml_file`（绝对路径或可解析为绝对路径）
  - `yaml_line`（1-based）
  - `field`（例如 `loader|call_by|retry.should_retry`）
- 当 `symbol_key` 可静态解析到 Python 定义时，item MUST 包含 `python_locations`（数组，元素至少包含 `file_path` 与 `range`）。
- 失败时 MUST 返回 `ok=false` + 可诊断 message（不得 crash / 退出）。

#### Scenario: dumpYamlPythonReferences returns at least one ref for a YAML with loader
- **GIVEN** 某 YAML 包含 `loader: "pkg.mod:func"`
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.dumpYamlPythonReferences`
- **THEN** server MUST 返回 `ok=true`
- **AND** `references` MUST 至少包含一条 `symbol_key=pkg.mod:func` 的记录

### Requirement: executeCommand MUST support `scalim.checkYamlPythonConsistency` (project-scoped inconsistencies)
系统 MUST 通过 `workspace/executeCommand` 暴露一个一致性检查命令：

- command id MUST 为 `scalim.checkYamlPythonConsistency`
- arguments MUST 允许为空；当提供时，arguments MUST 支持传入一个 document URI 以确定 project discovery 上下文
- 成功时 MUST 返回 JSON 可序列化 payload，且 MUST 至少包含：
  - `ok`（bool）
  - `inconsistencies`（数组）
- 每个 inconsistency item MUST 至少包含：
  - `symbol_key`
  - `yaml_refs`（数组，元素至少包含 `yaml_file` 与 `yaml_line`）
  - `reason`（可读失败原因）
- 失败时 MUST 返回 `ok=false` + 可诊断 message（不得 crash / 退出）。

#### Scenario: checkYamlPythonConsistency returns empty list when no inconsistencies
- **GIVEN** 当前项目引用索引中不存在 broken refs
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.checkYamlPythonConsistency`
- **THEN** server MUST 返回 `ok=true`
- **AND** `inconsistencies` MUST 为空数组

### Requirement: YAML diagnostics MUST include broken YAML→Python refs when reference_sync is enabled
当 `scalim.yaml yaml_dsl.lsp.reference_sync.enabled=true` 且 `show_inconsistency_diagnostics=true` 时，server MUST 将 broken YAML→Python refs 作为附加 diagnostics 发布，并满足：

- 对于包含不可解析 Python 引用（`loader/call_by/retry.should_retry`）的 DSL YAML，server MUST 在该 YAML 的 diagnostics 中附加至少一条 error diagnostic。
- diagnostic MUST 尽可能指向引用字符串范围（可降级到字段级或文件级 range），且 MUST 包含稳定的 `code`（例如 `broken-yaml-python-ref`）。
- server MUST NOT 因一致性检查失败而影响既有 schema/validator diagnostics 输出（仅追加，不替换）。

#### Scenario: broken ref yields an additional diagnostic
- **GIVEN** 某 DSL YAML 包含 `loader: "pkg.mod:missing_func"`
- **WHEN** client 请求 diagnostics
- **THEN** server MUST 发布至少一条 `code=broken-yaml-python-ref` 的 diagnostic
