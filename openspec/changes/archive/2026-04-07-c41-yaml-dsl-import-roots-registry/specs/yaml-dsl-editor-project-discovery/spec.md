# yaml-dsl-editor-project-discovery Specification

## MODIFIED Requirements

### Requirement: Editor project discovery MUST support nearest-wins `scalim.yaml` with zero-config fallback
系统 MUST 为编辑器/LSP 提供稳定的项目发现逻辑,用于确定 project root、YAML 允许根与 Python roots:

- 系统 MUST 支持从入口 YAML 文件所在目录向上查找最近的 `scalim.yaml`(nearest-wins)作为项目配置文件
- 当未找到 `scalim.yaml` 时,系统 MUST 以入口 YAML 所在目录作为默认 project root
- discovery 输出 MUST 明确返回: `project_root`、`scalim_yaml_path`(可为空)、`python_roots` 与 `allowed_yaml_roots`

当发现的 `scalim.yaml` 存在时，系统 MUST 从中读取以下可选配置（作为 discovery 的输入）：

- `yaml_dsl.import_roots`（用于 imports 的 alias 重写与默认 allow-roots 扩展）
- `yaml_dsl.lsp.python_roots`（用于静态解析 Python 引用的搜索根；相对 `scalim.yaml` 所在目录）

#### Scenario: nearest-wins discovery finds the closest scalim.yaml
- **GIVEN** 某工作区存在多层级 `scalim.yaml`
- **WHEN** 编辑器对某个子目录内的 YAML 执行 discovery
- **THEN** 系统 MUST 选择距离该 YAML 最近的 `scalim.yaml` 作为配置输入

