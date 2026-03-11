## MODIFIED Requirements

### Requirement: call_by 派生字段函数调用
系统 SHALL 支持在派生字段中声明 `call_by` 作为函数调用入口,其值为字符串 `reference(args...)`.
`call_by` 仅允许出现在派生字段(顶层 `fields`)中,并与 `compute` 互斥.
系统 SHALL 复用 loader 的 Python 引用解析与 allowlist 机制解析 `reference`.
系统 SHALL 额外支持 `reference` 的 module path 使用 Python 风格相对模块引用前缀 `.` / `..`(例如 `.helpers:to_text(status)`),其基准为 YAML 文件所在目录对应的“当前 module 路径”(由运行时根据 `yaml_path` 计算).
系统 SHALL 允许 `call_by` 参数中包含 Python 字面量与空白,并忽略参数周围空白.
系统 SHALL 拒绝非 Python 字面量(如 `true/false/null`).

#### Scenario: 基本 call_by 解析
- **WHEN** `call_by: "myapp.enums:get_status_text(status)"`
- **THEN** 解析出函数引用 `myapp.enums:get_status_text` 与参数 `status`,并生成派生字段计算函数

#### Scenario: 相对 call_by 引用被归一化
- **GIVEN** YAML 文件位于 module 路径 `myapp.reports` 对应目录
- **WHEN** `call_by: ".helpers:to_text(status)"`
- **THEN** 解析 MUST 将其归一化为绝对引用 `myapp.reports.helpers:to_text`

#### Scenario: allowlist 缺失
- **WHEN** 运行时未提供 allowlist 且配置包含 `call_by`
- **THEN** 解析失败并提示需要 allowlist
