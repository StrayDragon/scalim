# demand-dsl Specification

## Purpose
实现 YAML DSL 的加载、结构校验与 IR 转换流程,覆盖 main_source/sources/fields/relations 等配置,并在解析阶段使用安全 resolver 解析 loader 引用与 allowlist 限制,生成 DemandIr 供计划构建使用.

## Context
**FR001: 用户侧代码DSL**

用户侧配置需要有一种简单且符合直觉的用户侧代码配置,能清楚明白的表达数据源之间的血缘关系等元信息.

框架需要这些元信息:
- 怎么获取数据(数据源函数、查询条件)
- 数据间的联系:数据源们的血缘关系
- 数据源自身数量大小信息

核心概念:Demand(需求)、Source(数据源)、Field(字段)、Relation(关系).

## Related Concepts
- YAML DSL 加载器
- 配置校验器
- IR 转换器
- YAML 编译器
- 运行时入口
- 安全引用解析 (resolver/allowlist)
- Callable preflight 检查
- Loader retry 策略

## Requirements

### Requirement: 顶层结构与 IR 转换规则
系统 SHALL 在加载 YAML 时解析 `name`、`main_source`、`sources`、`fields`,并可选解析 `relations`、`output` 与 `guardrails`.
- `dsl_version` 字段不再支持;配置中出现 `dsl_version` MUST 被视为未知字段并在校验中失败.
- legacy 字段(`relations_sql_like`、`relations_graph`、`foreign_key`、`target`、`from`、`via`、`column`、`pk`、`pk_transform`、`derived`)一律拒绝.
- `name`、`main_source` 为必填项;`sources` 可缺省(缺省视为 `{}`)且允许为空对象;顶层 `fields` 可缺省.
- `main_source` 为对象结构(至少包含 `source_id` 与 `loader`);`sources` 仅包含非主源数据源.
- 源字段在 `main_source.fields` 与 `sources.*.fields` 内声明;顶层 `fields` 仅用于派生字段.
- `guardrails` 为可选对象结构,用于启用运行时护栏配置;未提供时默认关闭.
系统 SHALL 将 `guardrails.enabled`、`guardrails.mode`、`guardrails.loader.validate_result`、`guardrails.loader.required_fields`、`guardrails.relations.*_max_rate`、`guardrails.loader.on_transform_error`、`guardrails.compute.on_error` 等配置映射到运行时策略模型.
系统 SHALL 支持使用 `_templates` 中的 YAML anchor/alias 复用 `guardrails.*` 下的字段列表配置(例如 `guardrails.loader.required_fields`).
系统 SHALL 将 YAML 配置转换为 DemandIr,验证 `main_source.source_id` 不与 sources 冲突且字段引用的数据源存在.

#### Scenario: sources 缺省视为 {}
- **WHEN** YAML 配置未提供顶层 `sources`
- **THEN** 配置校验应通过且系统应将 `sources` 视为 `{}` 继续解析与转换

#### Scenario: dsl_version 被拒绝
- **WHEN** YAML 配置包含 `dsl_version`
- **THEN** 校验失败并报告未知字段路径

#### Scenario: legacy 字段被拒绝
- **WHEN** YAML 配置包含任一 legacy 字段
- **THEN** 校验失败并报告字段路径

#### Scenario: main_source 与 sources 冲突
- **WHEN** `main_source.source_id` 与 `sources` 中某个 `source_id` 重复
- **THEN** IR 转换应失败并报告冲突错误

#### Scenario: guardrails 缺省
- **WHEN** YAML 未声明 `guardrails`
- **THEN** 运行时护栏保持关闭

#### Scenario: guardrails 解析
- **WHEN** YAML 包含 `guardrails.enabled: true`
- **THEN** IR/运行期配置应启用护栏

### Requirement: source_id and sources keys MUST be valid identifiers and validated fail-fast
系统 MUST 对以下标识执行一致的 identifier 校验,并在 validate/schema validate 阶段 fail-fast(避免 compile/runtime 才失败):

- `main_source.source_id`
- `sources` mapping keys(每个 source 的 `source_id`)

identifier 规则 MUST 为正则: `^[a-zA-Z_][a-zA-Z0-9_]*$`.

并且当 source 声明存在时:

- `main_source.loader` MUST 为非空字符串
- `sources.<id>.loader` MUST 为非空字符串
- `sources.<id>.key` MUST 为非空字段名(或非空字段名列表)

#### Scenario: invalid source_id is rejected early
- **WHEN** `main_source.source_id` 或 `sources` 的 key 为 `""` 或 `"1abc"`
- **THEN** YAML DSL 校验 MUST 失败
- **AND** 错误 MUST 可定位到 `main_source.source_id` 或 `sources`(并指出非法 key)

#### Scenario: empty loader/key is rejected early
- **WHEN** `sources.orders.loader: ""` 或 `sources.orders.key: ""`
- **THEN** YAML DSL 校验 MUST 失败
- **AND** 错误 MUST 指向 `sources.orders.loader`/`sources.orders.key`

### Requirement: unknown fields 诊断提供 suggestions(CLI/库一致)
系统 SHALL 在 YAML DSL 校验阶段识别 unknown fields,并在 `validate_report` 的 issues 中报告其 path 与可读消息.
系统 MUST 为 unknown fields 提供 1~3 个 suggestions(基于 JSON Schema properties 的近似匹配),且 suggestions 输出顺序 MUST 稳定(deterministic).
系统 MUST 忽略以 `_` 开头的字段(例如 `_templates`)的 unknown-field 检测.
系统 MUST 支持 strict 模式:当 strict 启用时 unknown-field issues 以 error 级别报告;否则以 warning 级别报告.

#### Scenario: root unknown field 提示建议
- **WHEN** 配置根节点包含 unknown field `main_sorce`
- **THEN** `validate_report` MUST 报告 path 为 `main_sorce` 的 issue
- **THEN** 该 issue MUST 包含 suggestions 且包含 `main_source`

#### Scenario: nested unknown field 提示建议
- **WHEN** `main_source` 对象包含 unknown field `sourceid`
- **THEN** `validate_report` MUST 报告 path 为 `main_source.sourceid` 的 issue
- **THEN** 该 issue MUST 包含 suggestions 且包含 `source_id`

### Requirement: Loader 引用解析与 allowlist
系统 SHALL 支持 `module.path.function` 与 `module.path:obj.method` 两种 loader 引用格式,并在加载阶段校验格式、在 IR 转换阶段解析引用.
系统 SHALL 额外支持在 module path 上使用 Python 风格相对模块引用前缀 `.` / `..`(例如 `.loaders:load_orders`, `..common.transforms:fixup`).

相对引用规则:
- 相对引用的基准为 **YAML 文件所在目录** 对应的"当前 module 路径"(由运行时根据 `yaml_path` 计算).
- 相对 module 引用 MUST 在 allowlist 校验与实际导入解析前被归一化为绝对引用字符串.
- 当无法从 `yaml_path` 推导出"当前 module 路径"(例如 YAML 不在 `sys.path` 可导入目录下,或路径段不是合法 identifier)时,系统 MUST 拒绝相对引用并给出可操作的错误信息(例如提示改用绝对引用或调整 YAML 放置位置/`PYTHONPATH`).
系统 MUST 在所有可能解析 Python 引用的 YAML DSL 入口上默认启用 allowlist 安全边界(包括但不限于 `run/compile` 与对外导出的转换器);缺失 allowlist 时必须报错,提供 allowlist 时必须拒绝名单外模块或函数.
系统 MUST 支持对 class-style 引用在 `allowed_functions` 中精确到完整 attr 链的匹配(例如 `pkg.mod:Obj.safe`),不得仅因为允许了入口对象就允许其所有可调用属性.

#### Scenario: loader 引用非法
- **WHEN** loader 引用格式无效(不符合 dotted/class-style)
- **THEN** 配置加载 MUST 报校验错误并拒绝转换

#### Scenario: 相对 loader 引用被归一化
- **GIVEN** YAML 文件位于 module 路径 `myapp.reports` 对应目录
- **WHEN** `main_source.loader: ".loaders:load_orders"`
- **THEN** 解析 MUST 将其归一化为绝对引用 `myapp.reports.loaders:load_orders`

#### Scenario: 相对 loader 引用超出根层级被拒绝
- **GIVEN** YAML 文件位于 module 路径根层级
- **WHEN** loader 引用使用 `..` 前缀超出 module 根
- **THEN** 解析 MUST 失败并提示相对引用层级超出当前 module 根

#### Scenario: allowlist missing 时拒绝解析
- **WHEN** 调用方未提供 allowlist(allowed_modules/allowed_functions 均为空)
- **THEN** 系统 MUST 拒绝解析并提示必须提供 allowlist
- **AND** 此约束 MUST 适用于 `run/compile` 入口与对外导出的转换器

> NOTE: 显式 opt-in 的不安全模式仅用于测试/演示场景(例如兼容旧代码或本地快速验证).对于不可信 YAML/配置输入,不安全模式属于高风险 footgun,必须避免启用.

#### Scenario: class-style allowlist 精确到方法
- **GIVEN** allowlist 仅允许 `pkg.mod:Obj.safe`
- **WHEN** YAML loader/call_by 引用解析尝试解析 `pkg.mod:Obj.safe`
- **THEN** 解析通过
- **WHEN** 引用解析尝试解析 `pkg.mod:Obj.unsafe`
- **THEN** 解析 MUST 失败并报告 allowlist 拒绝

### Requirement: callable preflight MUST run before building execution request
系统 MUST 在 demand runtime compile 中引入明确的 callable preflight 阶段,并保证该阶段发生在:

- resolver/allowlist/builtin vocabulary 已就绪之后
- DemandIr 与 ExecutionRequest 构建之前

callable preflight MUST 覆盖所有可推理的 callable 误配（例如"参数绑定不匹配"/"固定 contract 不满足"）,并在失败时直接 fail-fast 抛出配置/编译错误。

（包含但不限于: `call_by` 绑定错误、`compute` SAFE_FUNCTIONS 的可推理调用形态错误、`sources.*.normalize.call_by` / `retry.should_retry` 签名不匹配、以及 loader `params` kwargs keys 与签名不一致。）

#### Scenario: preflight prevents silent compute swallowing
- **GIVEN** 某派生字段 `call_by` 将位置参数传给 keyword-only 函数签名
- **WHEN** 调用方执行 demand `compile/run`
- **THEN** 系统 MUST 在 compile 阶段 fail-fast
- **AND** MUST NOT 继续进入 engine 执行并将该字段写为 `None`

#### Scenario: quiet guardrails does not suppress preflight errors
- **GIVEN** `guardrails.enabled=true` 且 `guardrails.mode=quiet`
- **AND** demand 配置中存在可推理的 callable preflight 失败（例如 `call_by` 参数绑定不匹配）
- **WHEN** 调用方执行 demand `compile/run`
- **THEN** 系统 MUST 仍然 fail-fast 抛出编译错误

### Requirement: Source/Bind 结构与 keys 分片参数
系统 SHALL 支持为数据源定义 `key`、`lookup_cast`、`cache_mode`、`params` 与 `lookup_chunk_size`.

其中:
- `main_source.params` 与 `sources.<id>.params` MUST 被视为 loader kwargs 模板
- `main_source.params` 仅允许静态值与 `{$runtime: <name>}` 指令节点(禁止 `$keys/$rows`)
- `sources.<id>.params` 允许包含 `{$runtime: <name>}` 指令节点与 `$keys/$rows` 指令节点
- `sources.*.bind` 不再属于该能力的稳定 YAML authoring surface

当 `sources.<id>.params` 中使用 `$keys: {as: list}` 时,从 YAML 转换到运行时参数构建器的行为 MUST 产生稳定顺序列表。

#### Scenario: source params 模板构造动态参数
- **WHEN** source 配置使用 `params: {$keys: {as: set}}`
- **THEN** loader 调用 MUST 将 lookup_keys 转换为对应类型(set/list)并作为 kwargs 传入

#### Scenario: `sources.*.bind` 旧写法被拒绝
- **WHEN** source 配置使用旧的 `bind` 写法
- **THEN** 校验 MUST 失败并提示迁移到 `params` 模板
- **AND** 错误信息 MUST 包含可直接照抄的替换建议片段

#### Scenario: `$keys.as=list` 顺序稳定
- **WHEN** source 配置 `params` 模板中使用 `$keys: {as: list}`
- **THEN** 运行时传给 loader 的 keys 列表顺序 MUST 稳定(deterministic)

### Requirement: 使用语义清晰的配置 key 常量
系统 MUST 使用语义清晰且无歧义的 key 常量公开命名,并在解析器/校验器中统一使用该命名.

以下命名 MUST 生效:
- `BIND_KEY_CONFIG_KEYS`
- `MEMORY_OPTIMIZATION_KEYS`
- `RELATION_CONFIG_KEYS`
- `RELATIONS_CONFIG_KEYS`

旧命名(`BIND_KEYS_KEYS`、`MEMORY_OPT_KEYS`、`RELATION_KEYS`、`RELATIONS_KEYS`)MUST NOT 继续作为公开常量提供.

#### Scenario: 解析器使用新常量
- **WHEN** 解析器执行 YAML `observability/relations` 解析
- **THEN** 解析路径 MUST 使用新常量命名(BIND_KEY_CONFIG_KEYS 等)

#### Scenario: 旧常量不可导入
- **WHEN** 调用方尝试导入旧常量名
- **THEN** 导入 MUST 失败

### Requirement: loader params templates support `{$runtime: <name>}` directives
系统 SHALL 允许在 loader kwargs 模板中声明 `{$init_var: <name>}` 指令节点,并在编译期将其解析为调用方提供的初始化变量.

占位符解析的适用位置为:
- `main_source.params`
- `sources.<id>.params`

#### Scenario: main_source.params 引用 init var
- **WHEN** `main_source.params` 中某个值等于 `{$init_var: end_datetime_user}`
- **AND** 调用方提供 `init_vars={"end_datetime_user": <value>}`
- **THEN** main source loader MUST 接收到解析后的值而不是占位符字符串

### Requirement: 字段/关系表达式默认行为
系统 SHALL 支持 relations.steps 中 `source.field_id` 点号表达式(含同源列表),并在源字段定义中当 `extract` 未声明时默认使用 field_id(等价于 `extract: <field_id>`).
系统 MUST 将 `relations.steps` 的 `source.<name>` 视为字段的 `field_id`(YAML key),并将其映射为运行时使用的 `data_key`.
系统 MUST 基于 `extract` 推导 `data_key`:
- 若 `extract` 编译后恰为单段 string,则 `data_key` 等于该段(支持 rename: `extract: <key_name>`)
- 否则 `data_key` MUST 回退为 `field_id`
系统 MUST 将源字段中的 legacy `field: ...` 视为不允许,并在校验/编译阶段 fail-fast,错误消息应包含可直接照抄的迁移提示: "请改用 extract: ...".
系统 SHALL 允许在 steps 中引用非主源 `sources.<id>.key` 中声明的 key 字段,即使该 key 未显式声明在 `sources.<id>.fields`.
系统 MUST 在 `<name>` 不存在于该 source 的声明字段(field_id)且也不在 `sources.<id>.key` 时,视为配置错误并在校验阶段失败.
系统 MUST 在同一 source 内禁止 field_id 与其他 field_id 的 data_key 重名;一旦出现即视为配置错误并在校验阶段失败.
系统 SHALL 允许同一 source 内多个 field_id 指向同一 data_key,且此情况不应触发歧义失败.

#### Scenario: 使用点号表达式定义 step
- **WHEN** step 定义为 `from: orders.customer_id` 与 `to: customers.customer_id`
- **THEN** 系统 MUST 正确解析为 from=(orders, customer_id) 与 to=(customers, customer_id)

#### Scenario: extract 未声明时使用默认值
- **WHEN** 源字段定义为 `user_id: { name: 用户ID }` 且未声明 `extract`
- **THEN** 系统 MUST 将该字段的 `extract` 默认等价为 `user_id`
- **AND** 该字段的 `data_key` MUST 为 `user_id`

#### Scenario: legacy field 写法被拒绝
- **WHEN** 某个源字段声明 `field: review_status`
- **THEN** 校验 MUST 失败并指向该字段路径
- **AND** 错误 MUST 给出可照抄的迁移提示: "请改用 extract: review_status"

#### Scenario: step 优先使用 field_id 映射
- **GIVEN** source `products` 定义字段 `product_category_id: {extract: category_id}`
- **WHEN** step 使用 `to: products.product_category_id`
- **THEN** 系统 MUST 解析为 data_key `category_id`

#### Scenario: step 使用 data_key 时校验失败
- **GIVEN** source `products` 定义字段 `product_category_id: {extract: category_id}`
- **WHEN** step 使用 `to: products.category_id`(直接使用 data_key)
- **THEN** 校验 MUST 失败并提示 steps 只能使用 field_id

#### Scenario: field_id 与其他 data_key 重名时校验失败
- **GIVEN** source `products` 定义 `category_id: {extract: category_id_v2}` 且 `product_category_id: {extract: category_id}`
- **WHEN** 配置被校验
- **THEN** 校验 MUST 失败并提示 field_id/data_key 命名冲突

#### Scenario: step 引用未知字段校验失败
- **GIVEN** source `products` 定义字段 `product_category_id: {extract: category_id}`
- **WHEN** step 使用 `to: products.unknown_field`
- **THEN** 校验 MUST 失败并提示引用未知字段

#### Scenario: 多个 field_id 映射同一 data_key 不视为歧义
- **GIVEN** source `products` 定义多个字段映射到同一 data_key(例如 `a: {extract: id}` 与 `b: {extract: id}`)
- **WHEN** step 使用 `to: products.a`
- **THEN** 系统 MUST 解析为 data_key `id` 且不报歧义错误

### Requirement: main_source 批次排序配置
系统 SHALL 支持在 `main_source` 中声明 `order_by`,其值为字符串列表;每项为字段 id,可使用前缀 `-` 表示 `desc`,不带前缀表示 `asc`.
`order_by` 为可选配置;未声明时不启用排序.
系统 SHALL 校验 `order_by` 每项为非空字符串,且去除前缀 `-` 后必须匹配主数据源字段 id.
系统 SHALL 将 `order_by` 转换为 IR 的排序键列表(字段 id + 方向),保持声明顺序作为排序优先级.

#### Scenario: 解析 asc/desc 列表
- **WHEN** `main_source.order_by: ["order_id", "-created_at"]` 且两字段均定义于 `main_source.fields`
- **THEN** IR 排序键 MUST 为 `(order_id, asc) -> (created_at, desc)`

#### Scenario: 非法 order_by 条目被拒绝
- **WHEN** `main_source.order_by` 包含非字符串、空字符串或仅 "-" 的条目
- **THEN** 校验 MUST 失败并报告对应字段路径

#### Scenario: 非主数据源字段被拒绝
- **WHEN** `main_source.order_by` 引用仅存在于 `sources.*.fields` 或派生字段的 field_id
- **THEN** 校验 MUST 失败并提示仅允许主数据源字段

### Requirement: batch_size 语义、校验与一致性
系统 MUST 支持在 YAML 顶层声明 `batch_size`,其语义、校验与一致性要求如下:

**语义定义:**
- `batch_size: null` 表示禁用分批(no-chunking)
- `batch_size: <int>=1` 表示按固定批大小分批
- 未声明 `batch_size` 时沿用系统默认分批策略

**校验规则(在所有校验入口一致):**
- 仅允许 `null` 或整数且 `>=1`
- 非法值必须在校验阶段失败,并报告 `batch_size` 路径
- schema-only 与 runtime semantic 校验 MUST 提供一致结论

**解析约束:**
- MUST 在解析阶段保留 `null` 语义,不得将显式 `null` 静默替换为默认批大小

#### Scenario: 显式 null 被保留
- **WHEN** YAML 声明 `batch_size: null`
- **THEN** 解析后的配置对象 MUST 保留 `batch_size=None` 并进入后续编译链路

#### Scenario: 未声明 batch_size 使用默认
- **WHEN** YAML 未声明 `batch_size`
- **THEN** 系统 MUST 使用默认分批策略并保持与历史默认行为一致

#### Scenario: 非法值被一致拒绝
- **WHEN** `batch_size` 为非法类型(`true`/`1.5`/`"oops"`)或非法取值(`0`/负数)
- **THEN** schema-only 与 runtime semantic 校验 MUST 均失败,且 issue 路径包含 `batch_size`

### Requirement: YAML DSL loader retry 配置
系统 SHALL 在 YAML DSL 中支持声明 loader retry policy:
- 顶层可选对象 `retry` 作为全局默认 policy
- `main_source.retry` 作为主数据源 loader 的覆盖 policy
- `sources.*.retry` 作为各非主数据源 loader 的覆盖 policy

上述 policy 对象字段语义 MUST 与 loader retry policy 规范一致.

#### Scenario: 顶层 retry 缺省
- **WHEN** YAML 未提供顶层 `retry`
- **THEN** YAML 校验与 IR 转换 MUST 继续通过,且执行期默认不启用重试

#### Scenario: anchor/merge 复用 retry 策略
- **GIVEN** `_templates.retry.db_default` 被声明为 anchor
- **WHEN** 顶层 `retry` 通过 merge 复用该 anchor,且 `sources.customers.retry.enabled=false`
- **THEN** 解析与转换 MUST 成功,且 customers loader 的 effective policy MUST 为 disabled

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

### Requirement: `normalize` 配置规则
系统 SHALL 在 `sources.<id>` 上支持可选对象 `normalize`,并将其用于 lookup source 的 whole-result normalization.
系统 MUST 拒绝 `main_source.normalize`.

#### Scenario: `sources.*.normalize` 通过校验
- **WHEN** `sources.order_recommends.normalize.kind: index_by_key`
- **THEN** YAML 校验与 IR 转换 MUST 通过

#### Scenario: `main_source.normalize` 被拒绝
- **WHEN** YAML 声明 `main_source.normalize`
- **THEN** 校验 MUST 失败并指出 `main_source.normalize` 路径

### Requirement: aggregate 派生字段支持依赖驱动求值 (DAG)
系统 MUST 将 `outputs.*.aggregate.fields` 中的 rank/post 字段视为同一套聚合后派生字段图(DAG),并在 finalize 阶段按拓扑序执行,以支持:

- `rank.by` / `rank.order_by` 引用聚合后派生字段(例如 ratio、all_integral)
- post 字段(例如 `call_by`)依赖其它 post 字段(例如 `score_by_rank` 的结果)
- 综合分后的二次排名(rank-after-post)

系统 MUST 检测循环依赖并给出可操作的错误提示.

#### Scenario: rank-by-ratio is supported
- **GIVEN** ratio 在 aggregate 内由派生字段产生
- **WHEN** rank 字段以 `by: ratio` 引用该派生字段
- **THEN** 编译期校验 MUST 通过,且运行时 MUST 产生稳定可预测的排名结果

#### Scenario: post depends on post is supported
- **GIVEN** `all_integral` 的 `call_by` 引用其它 post 字段(例如 `score1`/`score2`)
- **WHEN** demand 被编译并运行
- **THEN** 编译期校验 MUST 通过,且 `all_integral` MUST 使用依赖字段的计算结果

### Requirement: aggregate fields 支持 safe compute 派生字段 (`compute`)
系统 MUST 支持在 `outputs.*.aggregate.fields.<out_field_id>` 中声明 `compute: <expression>` 以产生聚合后派生字段,并满足:

- `compute` MUST 使用安全表达式引擎执行(与 `where`/顶层 `fields.*.compute` 一致的安全边界)
- `compute` 的依赖字段 MUST 在编译期被提取并用于 DAG 执行计划与循环依赖诊断
- `compute` 字段 MUST 可被 `rank.by`/`rank.order_by` 与其它派生字段(`compute`/`call_by`/`score_by_rank`)引用

#### Scenario: compute ratio then rank-by-ratio is supported
- **GIVEN** ratio 在 aggregate 内由 `compute` 产生(例如 `ratio = sum_a / sum_b`)
- **WHEN** rank 字段以 `by: ratio` 引用该派生字段
- **THEN** 编译期校验 MUST 通过,且运行时 MUST 产生稳定可预测的排名结果

#### Scenario: compute depends on post is supported
- **GIVEN** `total` 的 `compute` 引用其它 post 字段(例如 `s1`/`s2`)
- **WHEN** demand 被编译并运行
- **THEN** 编译期校验 MUST 通过,且 `total` MUST 使用依赖字段的计算结果

## Notes
- 当前仅支持 YAML DSL 与 IR 类构造;类式 Python DSL 尚未实现.
- rows 模式默认批次内复用;若 loader 依赖可变的 `batch_rows` 或有副作用,应在目标 source 的 `params` 模板中使用 `$rows: {cache_mode: none}` 禁用复用.
- 字段 transform、派生字段、关系与输出行为详见相关规范.
