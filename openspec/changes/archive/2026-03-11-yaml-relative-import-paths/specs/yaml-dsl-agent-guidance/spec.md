## ADDED Requirements

### Requirement: `scalim-yaml-dsl` skill 提示相对模块引用与 allowlist 配置
系统 MUST 更新 `artifacts/skills/scalim-yaml-dsl/**`,使其在解释 YAML DSL 的 Python 引用(loader / `call_by` / retry 回调)时覆盖相对模块引用语法:
- 允许 `.` / `..` 前缀的 module path,且其基准为 YAML 文件所在目录
- 相对引用在运行期会先归一化为绝对引用,并继续受 allowlist(`allowed_modules`/`allowed_functions`)约束
- 当 allowlist 不包含归一化后的模块前缀时,应提示如何调整 allowlist 或改用绝对引用

#### Scenario: 用户询问如何组织 loaders 与 YAML
- **WHEN** 用户希望将 YAML 与 loaders 放在同一目录/包,并减少 `myapp.xxx` 这类绝对路径重复
- **THEN** skill guidance MUST 提示可使用相对引用(例如 `.loaders:load_orders`)
- **AND** MUST 同时提示需要将归一化后的 module 前缀纳入 allowlist
