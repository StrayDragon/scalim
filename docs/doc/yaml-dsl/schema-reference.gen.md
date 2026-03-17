<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- Schema generator: `just gen-yaml-dsl-schema`
-->
# YAML Schema 参考(生成)

此页用于快速对齐 YAML DSL 的字段集合与 `required` 边界.

## Top-Level Fields
- `name`: type=string; 需求配置名称. - 必填, 用于标识当前配置
- `imports`: type=object; 片段文件导入别名映射. - key: alias - value: 片段文件路径(字符串) - V1 仅支持同级文件名: `x.yaml|x.yml` 或 `./x.yaml|./x.yml` - 禁止: 绝对路径/父目录/子目录/alias 前缀
- `$import`: $import 引用. - string: `<alias>(.<segment>)*` - list: 按顺序合并,后者覆盖前者,最终再被本地覆盖 - 仅支持 mapping 片段 - V1 仅支持同级文件导入(见顶层 `imports`)
- `_templates`: type=object; YAML anchor 模板集合. - 仅用于 YAML 复用(anchors) - 常用于 `fields` / `relations` / `retry`
- `description`: type=string; 配置描述(可选).
- `batch_size`: 批处理大小. - 未声明时使用默认值 - `null` 表示禁用分批(单批执行) - `>=1` 的整数表示固定分批大小
- `retry`: ref=loader_retry; Loader retry 策略. - 默认关闭: `enabled: false` - 启用后会对 loader 调用的瞬态错误做有限重试 - 需要提供 `should_retry` 回调(安全引用),用于决定是否重试 - 受硬上限保护: max_attempts<=5, max_elapsed_seconds<=20, max_delay_seconds<=5
- `main_source`: ref=main_source; 主数据源配置. - 必填: `source_id`, `loader` - `source_id` 不能出现在 `sources` 中 - `fields` 仅允许源字段(禁止 `compute`) - `order_by` 控制批次内写入顺序(字符串列表,`-` 前缀表示 desc)
- `sources`: type=object; 数据源配置映射, key 为 `source_id`. - 每个 source 必填: `loader`, `key` - 不允许包含 `main_source.source_id` - `fields` 仅允许源字段(禁止 `compute`)
- `fields`: type=object; 字段配置映射(仅用于派生字段). - 必须包含 `compute` 或 `call_by` - 不能与源字段同名(避免 source/derived 重名) - 支持 YAML anchor 复用
- `relations`: type=object; 命名关联关系映射(steps 模板). - 供 `fields.*.relation` 通过 string ref 或 YAML alias 复用 - string ref: `relation: <relation_id>` 引用 `relations.<relation_id>` - alias 复用: `relation: *<anchor>` (YAML anchor) - steps 必须是等值关联链, 参考 `relation.steps`
- `guardrails`: ref=guardrails; 运行时护栏配置. - 默认关闭 - 用于控制 loader/relations/compute 等运行期护栏策略
- `outputs`: type=array[ref=output_target]; 输出目标列表(有序). - 通过 `where` 分发到不同 sheet - 通过 `aggregate` 声明派生汇总输出 - 通过 `from` 复用字段集合与容器配置 - 不再支持旧写法: 顶层 `output:`
- `failure_policy`: type=string; 多输出失败策略. - `all_fail`: 任一目标失败即失败 - `primary_only`: 非主输出失败将被禁用但不阻断主输出
- `include_full_error_message`: type=boolean; 包含完整错误信息(可能包含敏感信息;默认 false).
- `meta`: ref=output_extra_sheet; 可选:启用 meta sheet. - `true` 表示启用并使用默认配置 - 对象形式可覆盖 sheet 名称与 workbook 路径
- `audit`: ref=output_extra_sheet; 可选:启用 audit sheet. - `true` 表示启用并使用默认配置 - 对象形式可覆盖 sheet 名称与 workbook 路径
- `observability`: ref=observability; 可观测性配置. 包含 `logging`、`performance`、`relations`、`viz`、`trace`、`row_gap` 与 `memory_opt` 子配置.

## Definitions

### `field`
- `$import`: $import 引用(支持 string 或 string list)
- `call_by`: type=string; 派生字段函数调用(函数引用 + 参数列表),与 compute 互斥
- `compute`: type=string; 派生字段计算表达式(使用 field_id 作为变量名)
- `extract`: type=string; 从当前 key 对应的 row value 中提取字段值的路径表达式(不是相对整个 loader-result mapping).
- `name`: type=string; 字段显示名称
- `relation`: 关系路径(支持 string ref / steps 对象 / YAML alias; alias 需先定义),表示从 main_source 到当前字段 source 的等值关联链 (例: relation: orders_to_customers)
- `source`: type=string; 字段来源的 source_id (例: source: orders)
- `value_cast`: type=string; enum=auto|int|str; 字段值转换(仅源字段),用于写入上下文/输出前的类型调整

### `guardrails`
- `$import`: $import 引用(支持 string 或 string list)
- `compute`: ref=guardrails_compute
- `enabled`: type=boolean; default=false; 启用运行时护栏(默认关闭)
- `loader`: ref=guardrails_loader
- `mode`: type=string; default=fast_fail; enum=quiet|fast_fail; 护栏模式(quiet/fast_fail)
- `relations`: ref=guardrails_relations

### `guardrails_compute`
- `$import`: $import 引用(支持 string 或 string list)
- `on_error`: type=string; enum=quiet|fast_fail; 派生字段 compute 异常策略(可选;默认继承 mode)

### `guardrails_loader`
- `$import`: $import 引用(支持 string 或 string list)
- `on_transform_error`: type=string; enum=quiet|fast_fail; 字段转换异常策略(可选;默认继承 mode)
- `required_fields`: type=array; 关键字段列表(缺失/None 触发护栏;支持 field_id 字符串或 YAML alias)
- `validate_result`: type=boolean; default=false; 校验 loader 返回结构(契约校验)

### `guardrails_relations`
- `$import`: $import 引用(支持 string 或 string list)
- `null_key_max_rate`: 关联 null_key 最大比例(0.0-1.0;未设置则不启用)
- `type_error_max_rate`: 关联 type_error 最大比例(0.0-1.0;未设置则不启用)

### `loader_retry`
- `$import`: $import 引用(支持 string 或 string list)
- `backoff`: type=string; default=exponential; enum=fixed|exponential; 退避策略(fixed/exponential)
- `base_delay_seconds`: default=0.2; 基础等待时间(秒)
- `enabled`: type=boolean; default=false; Loader retry 策略(可选;默认关闭)
- `jitter`: type=boolean; default=true; 启用 jitter(随机扰动)
- `max_attempts`: type=integer; default=3; 最大尝试次数(含首次)
- `max_delay_seconds`: default=2.0; 最大单次等待时间(秒)
- `max_elapsed_seconds`: default=10.0; 最大累计耗时(秒,包含 sleep)
- `should_retry`: type=string; 重试判定回调引用(安全引用,由 allowlist 约束)

### `logging`
- `$import`: $import 引用(支持 string 或 string list)
- `enabled`: type=boolean; default=true; 启用日志观测
- `renderer`: type=string; default=pretty; enum=pretty|logger; 日志渲染器(pretty/logger)

### `main_source`
- `$import`: $import 引用(支持 string 或 string list)
- `fields`: type=object; 主数据源字段配置映射, key 为 field_id
- `loader`: type=string; Python 可调用对象引用(支持绝对/相对模块引用;支持点式/类式)
- `order_by`: type=array[string]; 主数据源批次内排序字段列表(仅主数据源字段)
- `params`: type=object; 调用 loader 时透传的 kwargs 模板(支持 `{$init_var: <name>}`; sources 支持 `$keys/$rows`)
- `retry`: ref=loader_retry; Loader retry 策略(可选;默认关闭)
- `source_id`: type=string; 主数据源的 source_id

### `memory_opt`
- `$import`: $import 引用(支持 string 或 string list)
- `auto_report`: type=boolean; default=false; 自动输出摘要
- `enabled`: type=boolean; default=false; 启用内存优化统计
- `max_fields`: type=integer; default=0; 摘要字段上限

### `observability`
- `$import`: $import 引用(支持 string 或 string list)
- `logging`: ref=logging; 日志观测配置
- `memory_opt`: ref=memory_opt; 内存优化统计配置
- `performance`: ref=performance; 性能可观测性配置
- `relations`: ref=relations; 关联可观测性配置
- `row_gap`: ref=row_gap; 行缺口统计配置
- `trace`: ref=trace; 执行追踪配置
- `viz`: ref=viz; Scalim Viz 可视化输出配置

### `output_aggregate`
- `$import`: $import 引用(支持 string 或 string list)
- `distinct_on_overflow`: type=string; default=error; enum=error|truncate; distinct 护栏溢出策略(error/truncate)
- `fields`: type=object; 聚合输出字段映射(key 为 out_field_id)
- `group_by`: type=array[string]; 分组字段列表
- `max_distinct`: type=integer; default=0; max_distinct 护栏(0 表示不限制)
- `max_groups`: type=integer; default=0; max_groups 护栏(0 表示不限制)

### `output_container`
- `$import`: $import 引用(支持 string 或 string list)
- `allow_formulas`: type=boolean; default=false; 允许 Excel 公式(仅 workbook)
- `encoding`: type=string; default=utf-8; 文件编码(CSV 输出使用)
- `header_fields_output_by`: type=string; default=field_id; enum=field_id|name; 表头字段名来源: field_id/name
- `include_header`: type=boolean; default=true; 包含表头行
- `path`: type=string; 输出文件路径(相对路径以进程CWD为基准;自动mkdir父目录)
- `sheet`: type=string; Excel sheet 名称(仅 workbook)
- `streaming`: type=boolean; default=true; 启用流式输出(必须为 true)
- `type`: type=string; enum=workbook|csv; 输出容器类型(workbook/csv)
- `write_lock`: type=boolean; default=false; 写锁(仅 workbook)

### `output_extra_sheet`
- `$import`: $import 引用(支持 string 或 string list)
- `allow_formulas`: type=boolean; 可选:允许 Excel 公式(缺省使用 primary workbook 的容器配置)
- `path`: type=string; 可选:工作簿路径(缺省使用 primary workbook)
- `sheet`: type=string; sheet 名称
- `write_lock`: type=boolean; 可选:写锁(缺省使用 primary workbook 的容器配置)

### `output_target`
- `$import`: $import 引用(支持 string 或 string list)
- `aggregate`: ref=output_aggregate; 可选:派生汇总配置(声明后视为 derived output)
- `container`: ref=output_container; 输出容器配置(workbook/csv)
- `fields`: type=array; 明细输出字段顺序(field_id 列表; 支持 YAML alias)
- `from`: type=string; 可选:继承来源输出(name)
- `name`: type=string; 输出名称(name)
- `where`: type=string; 可选:过滤表达式(安全表达式)

### `performance`
- `$import`: $import 引用(支持 string 或 string list)
- `enabled`: type=boolean; default=false; 启用性能监控
- `metrics`: type=array[enum]; 要收集的指标类型 (duration/memory/cpu)
- `report`: ref=performance_report
- `sampling_interval`: type=integer; default=1; 资源采样间隔(批次数)
- `thresholds`: ref=performance_thresholds

### `performance_report`
- `$import`: $import 引用(支持 string 或 string list)
- `format`: type=string; default=console; enum=console|json|csv|none; 报告输出格式
- `include_details`: type=boolean; default=false; 包含详细统计
- `output`: type=string; 报告输出路径

### `performance_thresholds`
- `$import`: $import 引用(支持 string 或 string list)
- `batch_duration_warn`: 批次耗时告警阈值(秒)
- `memory_increase_warn`: 内存增长告警阈值(MB)

### `relation`
- `$import`: $import 引用(支持 string 或 string list)
- `steps`: type=array[object]; 按顺序定义等值关联链(from == to),系统不会重排 steps, 表示从 main_source 出发沿链路到达当前字段 source (例: steps: [{from: orders.customer_id, to: customers.customer_id}])

### `relation_report`
- `$import`: $import 引用(支持 string 或 string list)
- `format`: type=string; default=console; enum=console|json|none; 报告输出格式
- `output`: type=string; 报告输出路径

### `relations`
- `$import`: $import 引用(支持 string 或 string list)
- `enabled`: type=boolean; default=false; 启用关联可观测性
- `log_type_mismatch`: type=boolean; default=true; 记录类型不匹配日志
- `max_samples`: type=integer; default=1000; 最大采样数量
- `report`: ref=relation_report
- `sampling_rate`: default=0.01; 采样率(0.0-1.0)

### `row_gap`
- `$import`: $import 引用(支持 string 或 string list)
- `data_loader_names`: type=array[string]; 参与统计的 loader 列表
- `enabled`: type=boolean; default=false; 启用行缺口统计
- `primary_loader_name`: type=string; default=primary_keys; 主数据 loader 名称
- `sample_limit`: type=integer; default=5; 缺口采样数量

### `source`
- `$import`: $import 引用(支持 string 或 string list)
- `cache_mode`: type=string; default=none; enum=none|preload_forever; 缓存模式:none=不缓存,preload_forever=预加载永久缓存
- `fields`: type=object; 数据源字段配置映射, key 为 field_id
- `key`: 该 source loader 返回映射的 key 字段(支持复合键 tuple)
- `loader`: type=string; Python 可调用对象引用(支持绝对/相对模块引用;支持点式/类式)
- `lookup_cast`: type=object; 归一化 lookup key 的转换(对象结构); sep_first 会先截取首段再做 auto_normalize_key, 例: {name: sep_first, sep: ','}
- `lookup_chunk_size`: keys 模式 LoadRef 的 lookup_keys 分片大小(0/空表示不分片)
- `normalize`: type=object; 源代码级整体结果 `normalize`(在字段级 `extract` 之前对 `loader` 整体返回值整形)
- `params`: type=object; 调用 loader 时透传的 kwargs 模板(支持 `{$init_var: <name>}`; sources 支持 `$keys/$rows`)
- `retry`: ref=loader_retry; Loader retry 策略(可选;默认关闭)

### `source_field_inline`
- `$import`: $import 引用(支持 string 或 string list)
- `extract`: type=string; 从当前 key 对应的 row value 中提取字段值的路径表达式(不是相对整个 loader-result mapping).
- `name`: type=string; 字段显示名称
- `relation`: 关系路径(支持 string ref / steps 对象 / YAML alias; alias 需先定义),表示从 main_source 到当前字段 source 的等值关联链 (例: relation: orders_to_customers)
- `source`: type=string; 字段来源的 source_id (例: source: orders)
- `value_cast`: type=string; enum=auto|int|str; 字段值转换(仅源字段),用于写入上下文/输出前的类型调整

### `trace`
- `$import`: $import 引用(支持 string 或 string list)
- `enabled`: type=boolean; default=false; 启用执行追踪

### `viz`
- `$import`: $import 引用(支持 string 或 string list)
- `append`: type=boolean; default=false; 事件文件追加写入
- `enabled`: type=boolean; default=false; 启用 Scalim Viz 输出
- `env`: type=string; 运行环境标签
- `output_dir`: type=string; 输出目录(自动追加 scalim-viz)
- `output_path`: type=string; 事件输出文件路径(可选)
- `payload_policy`: type=string; default=summary; enum=none|summary|sample|full; 事件 payload 策略
- `run_name`: type=string; 运行名称
- `sample_size`: type=integer; default=5; sample 策略下的样本数量
- `snapshot_path`: type=string; 快照输出文件路径(可选)
- `trace_enabled`: type=boolean; default=false; 启用高频 trace 输出
- `use_default_output_dir`: type=boolean; default=false; 使用默认输出目录

## Notes
- 完整字段语义以 `scalim-cli yaml-dsl validate` 的运行时行为为准.
