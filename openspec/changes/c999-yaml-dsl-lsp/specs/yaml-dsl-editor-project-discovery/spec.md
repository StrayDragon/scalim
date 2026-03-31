## ADDED Requirements

### Requirement: Editor project discovery MUST support nearest-wins `scalim.yaml` with zero-config fallback
系统 MUST 为编辑器/LSP 提供稳定的项目发现逻辑,用于确定 project root、YAML 允许根与 Python roots:

- 系统 MUST 支持从入口 YAML 文件所在目录向上查找最近的 `scalim.yaml`(nearest-wins)作为项目配置文件
- 当未找到 `scalim.yaml` 时,系统 MUST 以入口 YAML 所在目录作为默认 project root
- discovery 输出 MUST 明确返回: `project_root`、`scalim_yaml_path`(可为空)、`python_roots` 与 `allowed_yaml_roots`

#### Scenario: nearest-wins discovery finds the closest scalim.yaml
- **GIVEN** 某工作区存在多层级 `scalim.yaml`
- **WHEN** 编辑器对某个子目录内的 YAML 执行 discovery
- **THEN** 系统 MUST 选择距离该 YAML 最近的 `scalim.yaml` 作为配置输入

### Requirement: Discovery MUST classify YAML as demand vs workflow deterministically
系统 MUST 为编辑器提供稳定的 YAML 类型分类(demand/workflow),并用于选择 diagnostics/schema 语义边界:

- 系统 MUST 允许通过项目配置显式覆盖 YAML 的类型（例如按 glob 或按目录规则）
- 若无显式覆盖,系统 MUST 使用默认启发式:
  - 当 YAML 根 mapping 包含键 `workflow` 且其值为 mapping 时,该文件 MUST 被分类为 workflow
  - 否则该文件 MUST 被分类为 demand

#### Scenario: workflow root key implies workflow classification
- **GIVEN** 某 YAML 根节点包含 `workflow: {...}`
- **WHEN** 编辑器执行类型分类
- **THEN** 该文件 MUST 被分类为 workflow
