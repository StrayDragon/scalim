# yaml-dsl-render-effective-yaml Specification

**状态: ✅ 已实现**

## Purpose
提供用于 review/debug/对拍的**库侧 API**,将“作者写的 demand YAML”渲染为 effective YAML(展开后的单文件等价配置),避免 imports/template 复用在 review 时变成黑盒。

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/effective_yaml.py` (effective YAML loads/dumps API)
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/imports.py` (imports/$import expansion)
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/template_precompile.py` (LiteJinja2 template precompile)
## Requirements
### Requirement: Library MUST render effective demand YAML by expanding template_vars and imports
系统 MUST 提供一个用于 review/debug/对拍的**库侧 API**,将“作者写的 demand YAML”渲染为 effective YAML(展开后的单文件等价配置)。

该 API MUST 支持 `loads/dumps` 形态(或等价接口):

- `load_effective_demand_yaml(<demand.yaml>, template_vars=...) -> mapping`
- `dump_effective_demand_yaml(<mapping>) -> yaml_text`

渲染行为 MUST 至少包含:

- 对 demand YAML 文本执行 template precompile(仅当调用方显式提供 template vars)
- 对 demand YAML mapping 执行 imports/$import expansion

输出约束 MUST 满足:

- 输出 MUST 不包含 `imports` 与 `$import`(已被展开)
- 输出 MUST 保留 `{$init_var: ...}` / `$keys` / `$rows` 等指令节点(它们属于运行期模板 AST)

#### Scenario: API renders effective YAML text
- **GIVEN** 调用方提供 `demand.yaml`
- **WHEN** 调用方执行 `dump_effective_demand_yaml(load_effective_demand_yaml(demand.yaml))`
- **THEN** MUST 返回有效的 YAML 文本

#### Scenario: API fails fast on import expansion errors
- **GIVEN** demand YAML 的 imports 存在 cycle 或类型冲突
- **WHEN** 调用方执行 `load_effective_demand_yaml(demand.yaml)`
- **THEN** MUST 失败(抛出异常)
- **AND** 错误信息 MUST 包含可诊断内容(至少包含 import trace 与 logical path)

### Requirement: editor effective expansion MUST support outputs.fields flatten and YAML aliases

为支撑 editor 侧导航与补全,系统 MUST 提供静态的 effective expansion 视图,至少覆盖:

- YAML anchors/aliases 与 merge key 的展开（对当前打开文档以内存态文本为准）
- `outputs[*].fields` 的 nested list flatten 规则（与运行时/validator 口径一致）

#### Scenario: outputs.fields alias is expanded for navigation
- **GIVEN** YAML 使用 anchor 定义字段列表 `detail_fields: &detail_fields [a, b]`
- **AND** `outputs[0].fields` 使用 alias 引用 `- *detail_fields`
- **WHEN** editor 侧请求 outputs.fields 的 completion/definition
- **THEN** effective expansion MUST 将该 outputs.fields 视为展开后的有效列表（至少包含 `a`、`b`）

