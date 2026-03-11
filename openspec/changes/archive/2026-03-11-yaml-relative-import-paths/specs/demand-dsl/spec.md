## MODIFIED Requirements

### Requirement: Loader 引用解析与 allowlist
系统 SHALL 支持 `module.path.function` 与 `module.path:obj.method` 两种 loader 引用格式,并在加载阶段校验格式、在 IR 转换阶段解析引用.
系统 SHALL 额外支持在 module path 上使用 Python 风格相对模块引用前缀 `.` / `..`(例如 `.loaders:load_orders`, `..common.transforms:fixup`).

相对引用规则:
- 相对引用的基准为 **YAML 文件所在目录** 对应的“当前 module 路径”(由运行时根据 `yaml_path` 计算).
- 相对 module 引用 MUST 在 allowlist 校验与实际导入解析前被归一化为绝对引用字符串.
- 当无法从 `yaml_path` 推导出“当前 module 路径”(例如 YAML 不在 `sys.path` 可导入目录下,或路径段不是合法 identifier)时,系统 MUST 拒绝相对引用并给出可操作的错误信息(例如提示改用绝对引用或调整 YAML 放置位置/`PYTHONPATH`).

系统 MUST 在所有可能解析 Python 引用的 YAML DSL 入口上默认启用 allowlist 安全边界(包括但不限于 `run/compile` 与对外导出的 `ConfigToIRConverter`);缺失 allowlist 时必须报错,提供 allowlist 时必须拒绝名单外模块或函数.
系统 MUST 支持对 class-style 引用在 `allowed_functions` 中精确到完整 attr 链的匹配(例如 `pkg.mod:Obj.safe`),不得仅因为允许了入口对象就允许其所有可调用属性.

#### Scenario: loader 引用非法
- **WHEN** loader 引用不符合 dotted/class-style 格式
- **THEN** 配置加载应报校验错误并拒绝转换

#### Scenario: 相对 loader 引用被归一化
- **GIVEN** YAML 文件位于 module 路径 `myapp.reports` 对应目录
- **WHEN** `main_source.loader: ".loaders:load_orders"`
- **THEN** 解析 MUST 将其归一化为绝对引用 `myapp.reports.loaders:load_orders`

#### Scenario: 相对 loader 引用超出根层级被拒绝
- **GIVEN** YAML 文件位于 module 路径 `myapp` 对应目录
- **WHEN** `main_source.loader: "..loaders:load_orders"`
- **THEN** 解析 MUST 失败并提示相对引用层级超出当前 module 根

#### Scenario: allowlist missing(run/compile)
- **WHEN** 调用 `run/compile` 且未提供 allowlist(allowed_modules/allowed_functions 均为 None)
- **THEN** 解析应失败并提示必须提供 allowlist

#### Scenario: allowlist missing(ConfigToIRConverter 默认安全)
- **WHEN** 调用方使用对外导出的 `ConfigToIRConverter` 且未显式提供 allowlist(例如未提供带 allowlist 的 resolver)
- **THEN** 系统 MUST 拒绝解析并提示必须提供 allowlist(除非调用方显式 opt-in 不安全模式)

> NOTE: 显式 opt-in 的不安全模式仅用于测试/演示场景(例如兼容旧代码或本地快速验证).对于不可信 YAML/配置输入,不安全模式属于高风险 footgun,必须避免启用.

#### Scenario: class-style allowlist 精确到方法
- **GIVEN** allowlist 仅允许 `pkg.mod:Obj.safe`
- **WHEN** YAML loader/call_by 引用解析尝试解析 `pkg.mod:Obj.safe`
- **THEN** 解析通过
- **WHEN** 引用解析尝试解析 `pkg.mod:Obj.unsafe`
- **THEN** 解析 MUST 失败并报告 allowlist 拒绝

### Requirement: `should_retry` 引用解析与 allowlist
系统 MUST 支持在 YAML 的 retry policy 中以安全引用字符串声明 `should_retry`(格式与 loader 引用一致:dotted/class-style).
系统 MUST 额外支持 `should_retry` 引用的 module path 使用相对模块前缀 `.` / `..`(与 loader 相同规则与基准).
系统 MUST 通过与 loader 引用相同的 allowlist 安全边界解析该引用(allowed_modules/allowed_functions).

#### Scenario: allowlist 缺失时 should_retry 被拒绝
- **WHEN** YAML 配置包含 `retry.should_retry`(或任一 `*.retry.should_retry`)
- **AND** 调用 `compile/run` 未提供 allowlist(allowed_modules/allowed_functions 均为空)
- **THEN** 系统 MUST 拒绝执行并提示必须提供 allowlist

#### Scenario: 相对 should_retry 引用被归一化
- **GIVEN** YAML 文件位于 module 路径 `myapp.reports` 对应目录
- **WHEN** `retry.should_retry: ".retry_policies:should_retry_transient"`
- **THEN** 解析 MUST 将其归一化为绝对引用 `myapp.reports.retry_policies:should_retry_transient`
