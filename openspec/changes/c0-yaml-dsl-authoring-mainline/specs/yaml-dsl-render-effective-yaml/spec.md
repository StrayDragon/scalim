## ADDED Requirements

### Requirement: Library MUST render effective demand YAML by expanding template_vars and imports
系统 MUST 提供一个用于 review/debug/对拍的**库侧 API**，将“作者写的 demand YAML”渲染为 effective YAML（展开后的单文件等价配置）。

该 API MUST 支持 `loads/dumps` 形态（或等价接口）：

- `load_effective_demand_yaml(<demand.yaml>, template_vars=...) -> mapping`
- `dump_effective_demand_yaml(<mapping>) -> yaml_text`

渲染行为 MUST 至少包含：

- 对 demand YAML 文本执行 template precompile（仅当调用方显式提供 template vars）
- 对 demand YAML mapping 执行 imports/$import expansion

输出约束 MUST 满足：

- 输出 MUST 不包含 `imports` 与 `$import`（已被展开）
- 输出 MUST 保留 `{$init_var: ...}` / `$keys` / `$rows` 等指令节点（它们属于运行期模板 AST）

#### Scenario: API renders effective YAML text
- **GIVEN** 调用方提供 `demand.yaml`
- **WHEN** 调用方执行 `dump_effective_demand_yaml(load_effective_demand_yaml(demand.yaml))`
- **THEN** MUST 返回有效的 YAML 文本

#### Scenario: API fails fast on import expansion errors
- **GIVEN** demand YAML 的 imports 存在 cycle 或类型冲突
- **WHEN** 调用方执行 `load_effective_demand_yaml(demand.yaml)`
- **THEN** MUST 失败（抛出异常）
- **AND** 错误信息 MUST 包含可诊断内容（至少包含 import trace 与 logical path）
