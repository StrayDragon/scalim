# field-compute Specification

**状态: ✅ 已实现**
## Purpose
定义源字段 `value_cast` 转换与派生字段 `compute/call_by` 的解析、校验与执行行为,并规范派生字段依赖推导(拒绝显式 `depends_on`)与表达式安全策略.

## Context
**FR002: 字段转换与派生**

用户侧配置需要支持字段值转换与计算字段:
- 支持将原始值转换为目标类型(如 "123" → 123)
- 支持派生字段依赖计算(如收入-成本)

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/security.py` (`SecureComputeEngine`)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/parsers/fields.py` (infer derived deps; reject explicit `depends_on`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/conversion.py` (derived IR build + constant compute detection)
- `src/IMPL_ROOT/execution/executor/operators/compute/executor.py` (compute execution)
- `src/IMPL_ROOT/execution/executor/operators/compute/errors.py` (compute error/guardrails)
- `src/IMPL_ROOT/utils/converters.py` (`value_cast:auto` helpers)
## Requirements
### Requirement: 字段值 value_cast
系统 SHALL 在字段值被加载或关联获取后应用 `value_cast` 转换,并支持以下取值:`auto`、`int`、`str`.

- `value_cast` 仅作用于源字段(非 compute 字段).
- 未声明 `value_cast` 时保持原值.

#### Scenario: 应用字段 value_cast
- **WHEN** 字段 `amount` 配置 `value_cast: int` 且原始值为 "123"
- **THEN** 写入结果应为整数 123

#### Scenario: 缺省不转换
- **WHEN** 字段未配置 `value_cast`
- **THEN** 系统应保留原始值

### Requirement: compute 识别/校验/安全约束
系统 SHALL 将顶层 `fields` 中含 `compute` 或 `call_by` 的字段视为派生字段,并在配置阶段校验:
- `compute` 与 `call_by` 必须且只能声明其一
- `compute`(若声明)必填且必须为非空字符串
- `call_by`(若声明)必填且必须为非空字符串
- `derived` 字段为非法配置
系统 SHALL 在 YAML 校验阶段:
- 当使用 `compute` 时,使用安全表达式引擎检查 `compute` 的语法与可用名称集合,仅允许安全 AST 节点与白名单函数调用
- 当使用 `compute` 时,系统 MUST 对表达式施加可配置的资源上限(例如:表达式长度、AST 节点/深度、可静态推导的 range/repeat 规模、常量字符串/序列字面量规模);当超过上限时校验 MUST 失败并报告触发的限制项
- 当使用 `call_by` 时,复用 loader 的 Python 引用解析与 allowlist 机制解析函数引用,并对参数进行语法与安全约束校验(仅允许字段名、Python 字面量与受控 `$ctx.*` 引用)
一元运算符支持 `+`、`-`、`~`、`not`(仅对 compute).

#### Scenario: 同时声明 compute 与 call_by
- **WHEN** 派生字段同时配置 `compute` 与 `call_by`
- **THEN** 校验失败并提示互斥

#### Scenario: 缺失 compute 与 call_by
- **WHEN** 派生字段未配置 `compute` 也未配置 `call_by`
- **THEN** 校验失败并提示派生字段必须声明其一

#### Scenario: compute 语法错误
- **WHEN** `compute` 表达式语法非法
- **THEN** 校验失败并提示表达式语法错误

#### Scenario: compute 引用未知名称
- **WHEN** `compute` 引用未定义的字段名(既不是已声明字段的 field_id,也不是受控上下文名)
- **THEN** 校验失败并提示未知名称/非法引用

#### Scenario: compute 表达式支持一元 not
- **WHEN** compute="not is_active" 且 is_active=True
- **THEN** 计算结果应为 False

#### Scenario: compute 超过资源上限被拒绝
- **WHEN** `compute` 表达式超过系统配置的资源上限(例如过长表达式、过深嵌套、过大的 range/repeat 或常量字面量)
- **THEN** 校验 MUST 失败并报告触发的限制项(例如 max_expression_len/max_ast_nodes/max_range_len 等)

### Requirement: 依赖推导规则与无依赖拒绝
系统 SHALL 在 compute 存在时处理依赖:
- 依赖一律从表达式中推导(按首次出现顺序去重).
- 派生字段不再支持 `depends_on` 配置;若出现该字段,系统 MUST 拒绝该配置并报告错误.
- 推导结果为空时,仅当表达式 AST 不包含 `Name`/`Call` 节点才允许该派生字段,并标记为常量 compute;否则 IR 构建阶段仍拒绝该派生字段.

#### Scenario: 常量表达式允许
- **WHEN** compute="1 + 2"
- **THEN** 该派生字段允许构建并标记为常量 compute

#### Scenario: 空依赖但含函数调用仍拒绝
- **WHEN** compute="int('1')"
- **THEN** IR 构建失败并提示派生字段必须至少有一个依赖

#### Scenario: 显式 depends_on 被拒绝
- **WHEN** compute="amount + 1" 且配置包含 depends_on
- **THEN** 配置校验失败并提示 `depends_on` 已移除

### Requirement: 派生字段执行与错误处理
系统 SHALL 按依赖拓扑顺序计算派生字段;计算异常(TypeError/ValueError/ZeroDivisionError 等)应写入 None 并触发 ErrorEvent.
系统 SHALL 对常量 compute 执行批次内复用: 在单个批次内只计算一次并复用结果,但仍按行触发 FieldComputeEvent/ErrorEvent.
系统 SHALL 保持含依赖或含函数调用的 compute 逐行计算,不使用常量缓存.

#### Scenario: 常量表达式复用且逐行触发事件
- **WHEN** compute="1 + 2"
- **THEN** 同一批次内仅计算一次,但每行仍触发 field compute 事件

#### Scenario: 含函数调用或依赖字段不复用
- **WHEN** compute="int(amount)" 或 compute 依赖字段 a
- **THEN** 该字段应按行计算(不缓存)

### Requirement: compute 表达式预编译并复用执行
系统 MUST 在 compute 表达式通过 AST 安全校验后将其预编译为 code object,并在派生字段按行计算时复用该 code object,避免对每行重复编译表达式字符串.

#### Scenario: eval 使用 code object
- **WHEN** 使用 `SecureComputeEngine.compile()` 编译一个 compute 表达式并对多行数据重复调用其 calculator
- **THEN** 执行期的 `eval(...)` MUST 接收 code object(而不是表达式字符串)

### Requirement: compute 编译缓存有上限(有界 LRU)
系统 MUST 对 `SecureComputeEngine` 的编译缓存实施上限,并在超过上限时淘汰最旧的缓存条目,保证缓存大小不随高基数表达式无限增长.

#### Scenario: cache size 不超过上限
- **WHEN** 在同一个 `SecureComputeEngine` 实例中编译超过缓存上限数量的不同表达式
- **THEN** 编译缓存大小 MUST 小于等于配置的缓存上限

### Requirement: call_by 派生字段函数调用
系统 SHALL 支持在派生字段中声明 `call_by` 作为函数调用入口,其值为字符串 `reference(args...)`.
`call_by` 仅允许出现在派生字段(顶层 `fields`)中,并与 `compute` 互斥.
系统 SHALL 复用 loader 的 Python 引用解析与 allowlist 机制解析 `reference`.
系统 SHALL 允许 `call_by` 参数中包含 Python 字面量与空白,并忽略参数周围空白.
系统 SHALL 拒绝非 Python 字面量(如 `true/false/null`).

#### Scenario: 基本 call_by 解析
- **WHEN** `call_by: "myapp.enums:get_status_text(status)"`
- **THEN** 解析出函数引用 `myapp.enums:get_status_text` 与参数 `status`,并生成派生字段计算函数

#### Scenario: call_by 支持 kwargs
- **WHEN** `call_by: "myapp.enums:get_status_text(status=status, ctx=$ctx)"`
- **THEN** 参数解析包含 `status` 与 `ctx`,并将 `ctx` 注入为上下文对象

#### Scenario: call_by 支持 Python 字面量
- **WHEN** `call_by: "pkg.fn(flag=True, default=None, ratio=1.5, label='ok')"`
- **THEN** 参数解析应识别 Python 字面量且通过校验

#### Scenario: 非 Python 字面量被拒绝
- **WHEN** `call_by: "pkg.fn(flag=true)"`
- **THEN** 校验失败并提示字面量不合法

#### Scenario: allowlist 缺失
- **WHEN** 运行时未提供 allowlist 且配置包含 `call_by`
- **THEN** 解析失败并提示需要 allowlist

### Requirement: call_by 上下文引用
系统 SHALL 支持在 `call_by` 参数中使用 `$ctx.<attr>` 引用受控上下文.
`$ctx` 仅允许访问以下属性: `row_id`、`batch_num`、`field_id`、`deps`、`values`;其它属性应被拒绝.

#### Scenario: 合法 ctx 属性
- **WHEN** `call_by` 使用 `$ctx.row_id`
- **THEN** 参数解析通过并在运行时传入 row_id

#### Scenario: 非法 ctx 属性
- **WHEN** `call_by` 使用 `$ctx.unknown`
- **THEN** 校验失败并提示非法上下文属性

## Notes
- 计算表达式会在编译阶段校验名称是否在依赖列表中;依赖由表达式自动推导(按首次出现顺序去重).
- `value_cast: auto` 使用 `auto_str_normalize`(详见 `src/IMPL_ROOT/utils/converters.py`).
