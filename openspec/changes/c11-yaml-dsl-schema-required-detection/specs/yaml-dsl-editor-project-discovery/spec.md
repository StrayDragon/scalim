## MODIFIED Requirements

### Requirement: Discovery MUST classify YAML as demand vs workflow deterministically
系统 MUST 为编辑器提供稳定的 YAML 类型分类(demand/workflow),并用于选择 diagnostics/schema 语义边界:

- 系统 MUST 允许通过项目配置显式覆盖 YAML 的类型（例如按 glob 或按目录规则）
- 若无显式覆盖,系统 MUST 使用 schema(required) 作为 SSOT 信号并保持确定性：
  - 当 YAML 根 mapping 满足 workflow schema 顶层 required（包含键 `workflow`），且其值为 mapping 时,该文件 MUST 被分类为 workflow
  - 否则当 YAML 根 mapping 同时包含键 `name` 与 `main_source`（demand schema 顶层 required）时,该文件 MUST 被分类为 demand
  - 否则系统 MUST 将该文件分类为 demand（用于兼容“正在编写中的 YAML”与解析失败降级）

#### Scenario: workflow root key implies workflow classification
- **GIVEN** 某 YAML 根节点包含 `workflow: {...}`
- **WHEN** 编辑器执行类型分类
- **THEN** 该文件 MUST 被分类为 workflow

#### Scenario: demand required keys imply demand classification
- **GIVEN** 某 YAML 根节点包含 `name: ...` 与 `main_source: ...`
- **WHEN** 编辑器执行类型分类
- **THEN** 该文件 MUST 被分类为 demand

