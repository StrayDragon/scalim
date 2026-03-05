# Scalim YAML DSL Reference

## Coverage Index
Top-level fields:
- name
- _templates
- description
- batch_size
- retry
- main_source
- sources
- fields
- relations
- guardrails
- output
- observability

Definitions:
- field
- guardrails
- guardrails_compute
- guardrails_loader
- guardrails_relations
- loader_retry
- logging
- main_source
- memory_opt
- observability
- output
- performance
- performance_report
- performance_thresholds
- relation
- relation_report
- relations
- row_gap
- source
- source_field_inline
- trace
- viz

## Top-Level Fields
- `name`: 需求配置名称.

- 必填, 用于标识当前配置 (examples: `order_report`)
- `_templates`: YAML anchor 模板集合.

- 仅用于 YAML 复用(anchors)
- 常用于 `fields` / `relations` / `retry`
- `description`: 配置描述(可选).
- `batch_size`: 批处理大小.

- 未声明时使用默认值
- `null` 表示禁用分批(单批执行)
- `>=1` 的整数表示固定分批大小 (default: 1000) (examples: null, 1000)
- `retry`: Loader retry 策略.

- 默认关闭: `enabled: false`
- 启用后会对 loader 调用的瞬态错误做有限重试
- 需要提供 `should_retry` 回调(安全引用),用于决定是否重试
- 受硬上限保护: max_attempts<=5, max_elapsed_seconds<=20, max_delay_seconds<=5

- `main_source`: 主数据源配置.

- 必填: `source_id`, `loader`
- `source_id` 不能出现在 `sources` 中
- `fields` 仅允许源字段(禁止 `compute`)
- `order_by` 控制批次内写入顺序(字符串列表,`-` 前缀表示 desc)
- `sources`: 数据源配置映射, key 为 `source_id`.

- 每个 source 必填: `loader`, `key`
- 不允许包含 `main_source.source_id`
- `fields` 仅允许源字段(禁止 `compute`)
- `fields`: 字段配置映射(仅用于派生字段).

- 必须包含 `compute` 或 `call_by`
- 不能与源字段同名(避免 source/derived 重名)
- 支持 YAML anchor 复用
- `relations`: 命名关联关系映射(steps 模板).

- 供 `fields.*.relation` 通过 YAML alias 复用
- alias 需先定义 (YAML anchor)
- steps 必须是等值关联链, 参考 `relation.steps`
- `guardrails`: 运行时护栏配置.

- 默认关闭
- 用于控制 loader/relations/compute 等运行期护栏策略
- `output`: 输出配置.

- 可选: 不写 `output` 时使用默认输出策略
- 推荐: 把 `YAML` 当模板使用,在 Python 调用侧用 `overrides.output.*` 覆盖输出策略
- 默认 `format: csv`
- 字段重复时需要显式 `output.fields` 进行消歧
- `observability`: 可观测性配置.

包含 `logging`、`performance`、`relations`、`viz`、`trace`、`row_gap` 与 `memory_opt` 子配置.

## Definitions
### field
Properties:
- `call_by`: 派生字段函数调用(与 `compute` 互斥).

- 语法: `reference(args...)`
- 支持位置参数与 kwargs
- Python 字面量: `1`/`1.5`/`'ok'`/`True`/`False`/`None`
- 上下文引用: `$ctx` 或 `$ctx.<attr>`
- 可用 ctx 属性: `row_id`/`batch_num`/`field_id`/`deps`/`values` (examples: `myapp.enums:get_status_text(status)`, `myapp.enums:get_status_text(status=status, ctx=$ctx)`)
- `compute`: 派生字段计算表达式(与 `call_by` 互斥).

- 使用 `field_id` 作为变量名
- 必填, 不能为空 (examples: `revenue - cost`)
- `field`: 字段来源的列名.

- 缺省时等于字段 key
- `name`: 字段显示名称.

- `output.header_fields_output_by: name` 时作为表头
- `relation`: 关系路径(仅 steps 对象或 YAML alias; alias 需先定义),表示从 main_source 到当前字段 source 的等值关联链 (例: relation: *orders_to_customers)
- `source`: 字段来源的 `source_id`.

- 在 `main_source.fields` / `sources.<id>.fields` 中可省略
- 若显式提供, 必须与容器 `source_id` 一致
- `value_cast`: 字段值转换(仅源字段).

- `auto`: 自动转换
- `int`: 转为 int
- `str`: 转为 str (enum: auto, int, str) (examples: `auto`)

### guardrails
Properties:
- `compute`
- `enabled`: 启用运行时护栏.

- 默认关闭(不改变现有行为)
- 显式 enabled=true 才生效 (default: False)
- `loader`
- `mode`: 护栏模式.

- `quiet`: 不抛异常,但 best-effort 记录错误事件
- `fast_fail`: 首次触发即失败并终止 pipeline (enum: quiet, fast_fail) (default: fast_fail) (examples: `fast_fail`)
- `relations`

### guardrails_compute
Properties:
- `on_error`: 派生字段 compute 异常策略.

- 为空则继承 guardrails.mode (enum: quiet, fast_fail) (examples: `fast_fail`)

### guardrails_loader
Properties:
- `on_transform_error`: 字段转换异常策略.

- 作用于 extractor/value_cast/value_formatter/transform 等异常
- 为空则继承 guardrails.mode (enum: quiet, fast_fail) (examples: `fast_fail`)
- `required_fields`: 关键字段列表.

- 缺失/None 触发护栏
- 为空表示不启用缺失检查
- 每项支持 `field_id` 字符串或 YAML alias(指向已定义字段对象)
- YAML merge(`<<`) 会生成新对象并丢失 alias 身份; merge 产物请用字符串 field_id
- `validate_result`: 校验 loader 返回结构(契约校验).

- 启用时,契约违规始终 fast_fail(即使 mode=quiet) (default: False)

### guardrails_relations
Properties:
- `null_key_max_rate`: 关联 null_key 最大比例.

- 未设置则不启用阈值护栏
- v1 默认对全部关联 lookup step 生效
- `type_error_max_rate`: 关联 type_error 最大比例.

- 未设置则不启用阈值护栏
- v1 默认对全部关联 lookup step 生效

### loader_retry
Properties:
- `backoff`: 退避策略.

- `fixed`: 固定等待
- `exponential`: 指数退避 (enum: fixed, exponential) (default: exponential) (examples: `exponential`)
- `base_delay_seconds`: 基础等待时间(秒).

- fixed: 每次等待 base_delay
- exponential: base_delay * 2**(attempt-1) (default: 0.2) (examples: 0.2)
- `enabled`: Loader retry 策略.

- 默认关闭: `enabled: false`
- 启用后会对 loader 调用的瞬态错误做有限重试
- 需要提供 `should_retry` 回调(安全引用),用于决定是否重试
- 受硬上限保护: max_attempts<=5, max_elapsed_seconds<=20, max_delay_seconds<=5


注意:
- 当 enabled=true 时需要提供 `should_retry`
- 若未提供 `should_retry`, 仅当 driver 注入提供回调时才允许启用 (default: False)
- `jitter`: 启用 jitter(随机扰动),避免重试风暴.

- true: 在 [0, delay] 区间内随机
- false: 精确使用 delay (default: True) (examples: true)
- `max_attempts`: 最大尝试次数(含首次调用).

- 受硬上限保护: <= 5 (default: 3) (examples: 3)
- `max_delay_seconds`: 最大单次等待时间(秒).

- 受硬上限保护: <= 5 (default: 2.0) (examples: 2.0)
- `max_elapsed_seconds`: 最大累计耗时(秒,包含 sleep).

- 受硬上限保护: <= 20 (default: 10.0) (examples: 10.0)
- `should_retry`: 重试判定回调引用.

- 形式与 loader 引用一致: `module.path:function` 或 `module.path:obj.method`
- 由 allowlist(allowed_modules/allowed_functions) 约束
- 签名: `should_retry(exc, ctx) -> bool` (examples: `myapp.retry:should_retry_db`)

### logging
Properties:
- `enabled`: 启用日志观测. (default: True)
- `renderer`: 日志渲染器.

- `pretty`: 输出到 pretty console(如 panel/table)
- `logger`: 输出到标准 logger (enum: pretty, logger) (default: pretty) (examples: `pretty`)

### main_source
Properties:
- `fields`: 主数据源字段配置映射.

- 仅允许源字段(禁止 `compute`)
- `source` 可省略或必须等于 `main_source.source_id`
- 支持 YAML anchor 复用
- `loader`: Python 可调用对象引用.

- `module.path:ClassName`
- `module.path:function`
- `module.path:obj.method` (examples: `myapp.loaders:load_orders`)
- `order_by`: 主数据源批次内排序字段列表.

- 每项为字段 id, 前缀 `-` 表示 desc
- 未配置时保持 loader 原始顺序
- 仅允许主数据源字段
- `params`: 调用 loader 时透传的静态参数字典.

- main_source.params: 直接以 kwargs 传给 main source loader
- sources.<id>.params: 仅在 bind/use_keys 或 bind/use_rows 时合并到 loader kwargs
- 当 source 使用 cache_mode: preload_forever 时,预加载调用为无参,不会传 sources.<id>.params
- `retry`: Loader retry 策略.

- 默认关闭: `enabled: false`
- 启用后会对 loader 调用的瞬态错误做有限重试
- 需要提供 `should_retry` 回调(安全引用),用于决定是否重试
- 受硬上限保护: max_attempts<=5, max_elapsed_seconds<=20, max_delay_seconds<=5

- `source_id`: 主数据源的 `source_id`.

- 必填
- 不能与 `sources` 的 key 重复

### memory_opt
Properties:
- `auto_report`: 自动输出摘要. (default: False)
- `enabled`: 启用内存优化统计. (default: False)
- `max_fields`: 摘要字段上限(0 表示不限制). (default: 0)

### observability
Properties:
- `logging`: 日志观测配置.

- 控制日志输出开启/关闭
- `memory_opt`: 内存优化统计配置.

- 汇总字段瘦身/行释放等事件
- `performance`: 性能可观测性配置.

- 关注耗时/内存/CPU 等指标
- `relations`: 关联可观测性配置.

- 关注关联步骤的采样与类型校验
- `row_gap`: 行缺口统计配置.

- 统计 loader 期望/实际行数差异
- `trace`: 执行追踪配置.

- 记录批次级执行步骤
- `viz`: Scalim Viz 可视化输出配置.

- 输出 viz_snapshot.json + viz_events.jsonl

### output
Properties:
- `encoding`: 文件编码(CSV 输出使用). (default: utf-8)
- `fields`: 输出字段顺序.

推荐显式对象:
- `{field_id: order_id, name: 订单ID}`

按 data_key 选择:
- `{field: order_real_name, source: orders, name: 订单名}`

Alias 复用(指向已定义字段对象):
- `*order_id`

注意:
- 每项必须是对象或 alias, 不支持纯字符串
- 可用选择器: `field_id`(字段 ID) 或 `field`(loader data_key); 歧义时必须加 `source`
- YAML merge(`<<`) 会生成新对象并丢失 alias 身份; merge 产物需包含 `field_id` 或 `field` 选择器
- 显式对象除选择器键(`field_id`/`field`/`source`)外的键会覆盖字段配置
- `format`: 输出格式.

- `csv`: CSV 文件
- `excel`: Excel 文件
- 默认 `csv` (enum: excel, csv) (default: csv) (examples: `csv`)
- `header_fields_output_by`: 表头字段名来源.

- `field_id`: 使用字段 ID
- `name`: 使用字段的 `name` (为空或等于 field_id 时回退为 field_id) (enum: field_id, name) (default: field_id) (examples: `field_id`)
- `include_header`: 包含表头行. (default: True)
- `path`: 输出文件路径.

- 为空则不生成文件
- 相对路径以运行时进程当前工作目录(CWD)为基准(不是 YAML 文件所在目录)
- 会自动创建父目录: `mkdir(parents=True, exist_ok=True)`
- 可能覆盖同名文件
- 注意: 该路径完全由配置控制, 不要对不可信 YAML 开启文件输出; 生产建议在受控工作目录/权限隔离环境运行
- `streaming`: 启用流式输出(按行写入).

- 推荐保持为 `true` 以降低内存占用(尤其是大批量 CSV/Excel 输出)
- 设为 `false` 时会使用列式 file sink, 可能在 close() 前缓存大量输出数据 (default: True)

### performance
Properties:
- `enabled`: 启用性能监控. (default: False)
- `metrics`: 要收集的指标类型.

- 可选: duration / memory / cpu
- `report`
- `sampling_interval`: 资源采样间隔(按批次计). (default: 1)
- `thresholds`

### performance_report
Properties:
- `format`: 报告输出格式.

- `console`: 控制台输出
- `json`: JSON 文件
- `csv`: CSV 文件
- `none`: 不输出报告 (enum: console, json, csv, none) (default: console) (examples: `console`)
- `include_details`: 包含详细统计. (default: False)
- `output`: 报告输出路径

### performance_thresholds
Properties:
- `batch_duration_warn`: 批次耗时告警阈值(秒)
- `memory_increase_warn`: 内存增长告警阈值(MB)

### relation
Properties:
- `steps`: 按顺序定义等值关联链(from == to),系统不会重排 steps, 表示从 main_source 出发沿链路到达当前字段 source (例: steps: [{from: orders.customer_id, to: customers.customer_id}])

### relation_report
Properties:
- `format`: 报告输出格式.

- `console`: 控制台输出
- `json`: JSON 文件
- `none`: 不输出报告 (enum: console, json, none) (default: console) (examples: `console`)
- `output`: 报告输出路径

### relations
Properties:
- `enabled`: 启用关联可观测性. (default: False)
- `log_type_mismatch`: 记录类型不匹配日志. (default: True)
- `max_samples`: 最大采样数量. (default: 1000)
- `report`
- `sampling_rate`: 采样率(0.0-1.0). (default: 0.01)

### row_gap
Properties:
- `data_loader_names`: 参与统计的 loader 列表.
- `enabled`: 启用行缺口统计. (default: False)
- `primary_loader_name`: 主数据 loader 名称. (default: primary_keys)
- `sample_limit`: 缺口采样数量. (default: 5)

### source
Properties:
- `bind`: 绑定配置(将 rows 或 lookup keys 传给 loader).

- 必须且只能设置一种: `use_rows` 或 `use_keys`
- `param` 为 loader 参数名
- v3-only: 旧写法 `bind: {param: ids}` / `to_bind: {param: ids}` 会被拒绝,请迁移为 `use_keys`/`use_rows`
- 若目标 source 未设置 `cache_mode: preload_forever`, 需要 `to_bind` 或 `sources.<id>.bind`
- `cache_mode`: 缓存模式.

- `none`: 不缓存
- `preload_forever`: 预加载并长期缓存
- 设为 `preload_forever` 时, 关联到该 source 的 step 可不配置 `to_bind` (enum: none, preload_forever) (default: none)
- `fields`: 数据源字段配置映射.

- 仅允许源字段(禁止 `compute`)
- `source` 可省略或必须等于当前 `source_id`
- 支持 YAML anchor 复用
- `key`: 该 source loader 返回映射的 key 字段.

- 单字段: `key: order_id`
- 复合键: `key: [region_id, institution_id]` (examples: `order_id`, ["region_id", "institution_id"])
- `loader`: Python 可调用对象引用.

- `module.path:ClassName`
- `module.path:function`
- `module.path:obj.method` (examples: `myapp.loaders:load_orders`)
- `lookup_cast`: 归一化 lookup key 的转换.

- `name`: auto / int / str / sep_first
- `auto` 会拒绝 float lookup key(避免歧义,返回 None 并忽略该键);
  若上游可能返回 float(例如 123.0/12.34),请用 `int`/`str` 显式归一化或在 loader 中修复
- `sep_first` 先按 `sep` 截取首段再做 normalize
- `lookup_chunk_size`: keys 模式 lookup_keys 分片大小.

- `0` / `null` 表示不分片
- `params`: 调用 loader 时透传的静态参数字典.

- main_source.params: 直接以 kwargs 传给 main source loader
- sources.<id>.params: 仅在 bind/use_keys 或 bind/use_rows 时合并到 loader kwargs
- 当 source 使用 cache_mode: preload_forever 时,预加载调用为无参,不会传 sources.<id>.params
- `retry`: Loader retry 策略.

- 默认关闭: `enabled: false`
- 启用后会对 loader 调用的瞬态错误做有限重试
- 需要提供 `should_retry` 回调(安全引用),用于决定是否重试
- 受硬上限保护: max_attempts<=5, max_elapsed_seconds<=20, max_delay_seconds<=5


### source_field_inline
Properties:
- `field`: 字段来源的列名.

- 缺省时等于字段 key
- `name`: 字段显示名称.

- `output.header_fields_output_by: name` 时作为表头
- `relation`: 关系路径(仅 steps 对象或 YAML alias; alias 需先定义),表示从 main_source 到当前字段 source 的等值关联链 (例: relation: *orders_to_customers)
- `source`: 字段来源的 `source_id`.

- 在 `main_source.fields` / `sources.<id>.fields` 中可省略
- 若显式提供, 必须与容器 `source_id` 一致
- `value_cast`: 字段值转换(仅源字段).

- `auto`: 自动转换
- `int`: 转为 int
- `str`: 转为 str (enum: auto, int, str) (examples: `auto`)

### trace
Properties:
- `enabled`: 启用执行追踪. (default: False)

### viz
Properties:
- `append`: 事件文件追加写入(可选).

- 默认 `false`: 每次运行会覆盖 `output_path` 对应文件,避免跨 run 混写
- 设为 `true` 时,将以 JSONL 追加写入(旧行为)
- `output_dir` 写入到按 run 隔离目录时,通常不需要开启 (default: False) (examples: false)
- `enabled`: 启用 Scalim Viz 输出. (default: False)
- `env`: 运行环境标签(可选).
- `output_dir`: 输出目录(自动追加 scalim-viz).

- 写入路径: output_dir/scalim-viz/<run_id>/viz_*.json
- 若 output_dir 已包含 scalim-viz,则直接使用
- 若显式配置 output_path/snapshot_path,则忽略该规则
- `output_path`: 事件输出文件路径(可选).
- `payload_policy`: 事件 payload 策略.

- `none`: 不输出 payload
- `summary`: 仅摘要
- `sample`: 抽样
- `full`: 全量 (enum: none, summary, sample, full) (default: summary) (examples: `summary`)
- `run_name`: 运行名称(可选).
- `sample_size`: sample 策略下的样本数量. (default: 5)
- `snapshot_path`: 快照输出文件路径(可选).
- `trace_enabled`: 启用高频 trace 输出(可选).

- `false`(默认): 仅输出编排级事件到 `viz_events.jsonl`
- `true`: 额外输出高频 trace 事件到 `viz_trace.jsonl`(例如 field/row/relation lookup)

建议: 默认关闭;需要深挖时在 UI 勾选加载 trace 并配合过滤/步进 lens 使用.

旧字段 `observability.viz.event_mode` 已移除,请使用 `trace_enabled`. (default: False) (examples: false)
- `use_default_output_dir`: 使用默认输出目录(~/.config/scalim-viz 等). (default: False)
