## ADDED Requirements

### Requirement: `scalim-yaml-dsl` skill documents `$keys/$rows` inline params directives
系统 MUST 更新 `artifacts/skills/scalim-yaml-dsl/**` 使其覆盖新的 params 模板指令写法,并将其作为首选方案用于解决 nested params 绑定问题.

skill 文档 MUST 至少包含:
- `$keys` 与 `$rows` 的最小示例
- `$rows` 会触发 rows barrier 的提示
- composite key 在 `$keys` 下保持 tuple 结构的说明
- `bind/to_bind` 到模板指令的迁移规则与常见错误诊断

#### Scenario: authoring 示例包含 `$keys`
- **WHEN** 用户请求编写一个 ref loader,需要把 lookup keys 注入到 `kwargs["params"]["..."]` 的嵌套位置
- **THEN** skill guidance MUST 给出 `$keys` 内联模板示例(而非建议编写 Python wrapper)

#### Scenario: upgrade guidance 指导从 bind 迁移到模板指令
- **WHEN** 用户请求将旧写法 `bind.use_keys.param` 升级为更直觉的 nested params 写法
- **THEN** skill guidance MUST 给出迁移后的 `$keys/$rows` 模板写法与校验命令

#### Scenario: old bind/to_bind 不再被建议
- **WHEN** 用户请求为 ref loader 生成 YAML
- **THEN** skill guidance MUST 不再输出 `bind/to_bind` 写法
- **AND** 必须以 `params` 模板作为默认方案
