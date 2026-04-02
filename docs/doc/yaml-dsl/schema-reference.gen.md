<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- `src/scalim/dsl/by_yaml/schema/workflow.gen.json`
- Schema generator: `just gen-yaml-dsl-schema`
-->
# YAML Schema 参考(生成)

此页用于快速对齐 YAML DSL 的字段集合与 `required` 边界.

## Top-Level Fields
- `name` (required): type=string; 需求配置名称. - 必填, 用于标识当前配置
- `imports`: type=object; 片段文件导入别名映射. - key: alias - value: 片段文件路径(字符串) - V2 支持相对路径 fragments(解析基准: 当前 YAML 文件所在目录): - `./x.yaml` / `x.yaml` - `x/y.yaml`(子目录) - `../x.yaml`(父目录) - 支持(编辑器侧放宽,运行时校验为准): - alias 路径: `@/x.yaml`, `COMMON:/x.yaml`(需 `scalim.yaml` 显式配置) - 内置 preset: `scalim://yaml-dsl/presets/common.yaml`(仅本地白名单) - 禁止(以运行时为准): 绝对路径/非 `scalim://` 的 `URI scheme`/Windows 盘符/反斜杠分隔符等
- `_templates`: type=object; YAML anchor 模板集合. - 仅用于 YAML 复用(anchors) - 常用于 `fields` / `relations`
- `description`: type=string; 配置描述(可选).
- `main_source` (required): ref=main_source; 主数据源配置. - 必填: `source_id`, `loader` - `source_id` 不能出现在 `sources` 中 - `fields` 仅允许源字段(禁止 `compute`) - `order_by` 控制批次内写入顺序(字符串列表,`-` 前缀表示 desc)
- `sources`: type=object; 数据源配置映射, key 为 `source_id`. - 每个 source 必填: `loader`, `key` - 不允许包含 `main_source.source_id` - `fields` 仅允许源字段(禁止 `compute`)
- `fields`: type=object; 字段配置映射(仅用于派生字段). - 必须包含 `compute` 或 `call_by` - 不能与源字段同名(避免 source/derived 重名) - 支持 YAML anchor 复用
- `relations`: type=object; 命名关联关系映射(steps 模板). - 供 `fields.*.relation` 通过 string ref 或 YAML alias 复用 - string ref: `relation: <relation_id>` 引用 `relations.<relation_id>` - alias 复用: `relation: *<anchor>` (YAML anchor) - steps 必须是等值关联链, 参考 `relation.steps`
- `resources`: ref=resources; 可选:IO 资源声明. - 稳定入口: `resources.books` / `resources.files`
- `outputs`: type=array[ref=output_target]; 输出目标列表(有序; 可选). - 顶层 `outputs` 可省略,用于保持 demand YAML 可复用(通常仅承载需求本体) - 需要运行时动态指定输出(字段/路径/sheet/header 策略)时,推荐在 Python 调用侧使用与 YAML 同形的 `overrides.outputs` - 通过 `where` 分发到不同 sheet - 通过 `aggregate` 声明派生汇总输出 - 通过 `from` 复用字段集合与容器配置 - 不再支持旧写法: 顶层 `output:`
- `validate_unique_field_names`: type=boolean; 预检查: 字段有效展示名(`effective display name`)全局唯一. - 默认启用: 未声明时等价 `true` - 有效展示名定义: - 若 `field.name` 非空: 使用 `name` - 否则回退为 `field_id` - 仅当 `effective outputs` 会输出表头且 `header_fields_output_by: name` 时触发 - file: `write.include_header: true` 且 `write.header_fields_output_by: name` - book: 该 output 会输出表头,且 `write.header_fields_output_by: name` - 显式设置为 `false` 可关闭该检查(不推荐长期使用)
- `include_full_error_message`: type=boolean; 包含完整错误信息(可能包含敏感信息;默认 false).

## Definitions

### `book`
- `$import`: $import 引用(支持 string 或 string list)
- `allow_formulas`: type=boolean; default=false; xlsx_file: 允许 Excel 公式(可信输入显式 opt-out;默认 false)
- `budget`: ref=book_budget; xlsx_memory: 预算配置(必填)
- `export_xlsx`: ref=book_export_xlsx; xlsx_memory: 可选导出配置
- `kind`: type=string; enum=xlsx_file|xlsx_memory; book kind(xlsx_file/xlsx_memory)
- `path`: xlsx_file: 输出路径(字符串或 {$init_var: <name>})
- `write_defaults`: ref=book_write_defaults; 可选:默认写入语义与冲突策略
- `write_lock`: type=boolean; default=false; xlsx_file: 写锁(默认 false)

### `book_budget`
- `$import`: $import 引用(支持 string 或 string list)
- `max_sheets`: type=integer; sheet 数量预算(>=1)
- `max_total_cells`: type=integer; 总 cell 数预算(>=1)

### `book_export_xlsx`
- `$import`: $import 引用(支持 string 或 string list)
- `allow_formulas`: type=boolean; default=false; 允许 Excel 公式(可信输入显式 opt-out;默认 false)
- `path`: 导出 xlsx 的输出路径(字符串或 {$init_var: <name>})
- `write_lock`: type=boolean; default=false; 写锁(导出时;默认 false)

### `book_write_defaults`
- `$import`: $import 引用(支持 string 或 string list)
- `align_by`: type=string; default=field_id; enum=field_id|header; 字段对齐策略(field_id/header;仅 append 生效)
- `header_policy`: type=string; default=once; enum=once|always|never; 表头策略(once/always/never;仅 append 生效)
- `mode`: type=string; default=append; enum=sheet|append; 写入语义(sheet/append)
- `on_conflict`: type=string; default=error; enum=error|overwrite|skip; sheet 冲突策略(error/overwrite/skip;仅 sheet 生效)
- `on_mismatch`: type=string; default=error; enum=error|warn|skip; 字段不匹配策略(error/warn/skip;仅 append 生效)

### `field`
- `$import`: $import 引用(支持 string 或 string list)
- `call_by`: type=string; 派生字段函数调用(函数引用 + 参数列表),与 compute 互斥
- `compute`: type=string; 派生字段计算表达式(使用 field_id 作为变量名)
- `extract`: type=string; 从当前 key 对应的 row value 中提取字段值的路径表达式(不是相对整个 loader-result mapping).
- `name`: type=string; 字段显示名称
- `relation`: 关系路径(支持 string ref / steps 对象 / YAML alias; alias 需先定义),表示从 main_source 到当前字段 source 的等值关联链 (例: relation: orders_to_customers)
- `source`: type=string; 字段来源的 source_id (例: source: orders)
- `value_cast`: type=string; enum=auto|int|str|decimal; 字段值转换(仅源字段),用于写入上下文/输出前的类型调整

### `file`
- `$import`: $import 引用(支持 string 或 string list)
- `encoding`: type=string; default=utf-8; csv_file: 文件编码(默认 utf-8)
- `kind`: type=string; enum=csv_file; file kind(csv_file)
- `path`: csv_file: 输出路径(字符串或 {$init_var: <name>})

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
- `null_key_max_rate`: type=number; 关联 null_key 最大比例(0.0-1.0;未设置则不启用)
- `type_error_max_rate`: type=number; 关联 type_error 最大比例(0.0-1.0;未设置则不启用)

### `loader_retry`
- `$import`: $import 引用(支持 string 或 string list)
- `backoff`: type=string; default=exponential; enum=fixed|exponential; 退避策略(fixed/exponential)
- `base_delay_seconds`: type=number; default=0.2; 基础等待时间(秒)
- `enabled`: type=boolean; default=false; Loader retry 策略(可选;默认关闭)
- `jitter`: type=boolean; default=true; 启用 jitter(随机扰动)
- `max_attempts`: type=integer; default=3; 最大尝试次数(含首次)
- `max_delay_seconds`: type=number; default=2.0; 最大单次等待时间(秒)
- `max_elapsed_seconds`: type=number; default=10.0; 最大累计耗时(秒,包含 sleep)
- `should_retry`: type=string; 重试判定回调引用(安全引用,由 allowlist 约束)

### `main_source`
- `$import`: $import 引用(支持 string 或 string list)
- `fields`: type=object; 主数据源字段配置映射, key 为 field_id
- `loader`: type=string; Python 可调用对象引用(支持绝对/相对模块引用;支持点式/类式;支持内置 ^<id>)
- `order_by`: type=array[string]; 主数据源批次内排序字段列表(仅主数据源字段)
- `params`: type=object; 调用 loader 时透传的 kwargs 模板(支持 `{$init_var: <name>}`; sources 支持 `$keys/$rows`)
- `source_id`: type=string; 主数据源的 source_id

### `output_aggregate`

- Required: `fields`, `group_by`
- `distinct_on_overflow`: type=string; default=error; enum=error|truncate; distinct 护栏溢出策略(error/truncate)
- `fields` (required): type=object; 聚合输出字段映射(key 为 out_field_id)
- `group_by` (required): type=array; 分组字段列表
- `max_distinct`: type=integer; default=0; max_distinct 护栏(0 表示不限制)
- `max_groups`: type=integer; default=0; max_groups 护栏(0 表示不限制)

### `output_extra_sheet`
- `allow_formulas`: type=boolean; 可选:允许 Excel 公式(缺省使用 primary workbook 的容器配置)
- `path`: type=string; 可选:工作簿路径(缺省使用 primary workbook)
- `sheet`: type=string; sheet 名称
- `write_lock`: type=boolean; 可选:写锁(缺省使用 primary workbook 的容器配置)

### `output_target`

- Required: `name`
- `aggregate`: ref=output_aggregate; 可选:派生汇总配置(声明后视为 derived output)
- `fields`: type=array; 输出字段顺序(field_id/out_field_id 列表; 支持 YAML alias)
- `from`: type=string; 可选:继承来源输出(name)
- `name` (required): type=string; 输出名称(name)
- `to`: ref=output_to; 可选:输出目标绑定(to: file/book/sheet)
- `where`: type=string; 可选:过滤表达式(安全表达式)
- `write`: ref=output_write; 可选:写入策略覆盖(write)

### `output_to`
- `book`: type=string; 可选:目标 book_id
- `file`: type=string; 可选:目标 file_id
- `sheet`: type=string; 可选:目标 sheet 名称

### `output_write`
- `header_fields_output_by`: type=string; default=name; enum=field_id|name; 可选:表头字段名来源(field_id/name;默认 name)
- `include_header`: type=boolean; default=true; 可选:是否输出表头(默认 true)

### `relation`
- `$import`: $import 引用(支持 string 或 string list)
- `steps`: type=array[object]; 按顺序定义等值关联链(from == to),系统不会重排 steps, 表示从 main_source 出发沿链路到达当前字段 source (例: steps: [{from: orders.customer_id, to: customers.customer_id}])

### `resources`
- `$import`: $import 引用(支持 string 或 string list)
- `books`: type=object; books 资源映射(Excel book; key 为 book_id)
- `files`: type=object; files 资源映射(文件输出资源; key 为 file_id)

### `source`
- `$import`: $import 引用(支持 string 或 string list)
- `cache_mode`: type=string; default=none; enum=none|preload_forever; 缓存模式:none=不缓存,preload_forever=预加载永久缓存
- `fields`: type=object; 数据源字段配置映射, key 为 field_id
- `key`: 该 source loader 返回映射的 key 字段(支持复合键 tuple)
- `loader`: type=string; Python 可调用对象引用(支持绝对/相对模块引用;支持点式/类式;支持内置 ^<id>)
- `lookup_cast`: type=object; 归一化 lookup key 的转换(对象结构); sep_first 会先截取首段再做 auto_normalize_key, 例: {name: sep_first, sep: ','}
- `lookup_chunk_size`: keys 模式 LoadRef 的 lookup_keys 分片大小(0/空表示不分片)
- `normalize`: type=object; 源代码级整体结果 `normalize`(在字段级 `extract` 之前对 `loader` 整体返回值整形)
- `params`: type=object; 调用 loader 时透传的 kwargs 模板(支持 `{$init_var: <name>}`; sources 支持 `$keys/$rows`)

### `source_field_inline`
- `$import`: $import 引用(支持 string 或 string list)
- `extract`: type=string; 从当前 key 对应的 row value 中提取字段值的路径表达式(不是相对整个 loader-result mapping).
- `name`: type=string; 字段显示名称
- `relation`: 关系路径(支持 string ref / steps 对象 / YAML alias; alias 需先定义),表示从 main_source 到当前字段 source 的等值关联链 (例: relation: orders_to_customers)
- `source`: type=string; 字段来源的 source_id (例: source: orders)
- `value_cast`: type=string; enum=auto|int|str|decimal; 字段值转换(仅源字段),用于写入上下文/输出前的类型调整

## Workflow Schema

### Top-Level Fields
- `workflow` (required): type=object

### Definitions

#### `book`

- Required: `kind`
- `allow_formulas`: type=boolean; default=false; xlsx_file: 允许 Excel 公式(可信输入显式 opt-out;默认 false)
- `budget`: ref=book_budget; xlsx_memory: 预算配置(必填)
- `export_xlsx`: ref=book_export_xlsx; xlsx_memory: 可选导出配置
- `kind` (required): type=string; enum=xlsx_file|xlsx_memory; book kind(xlsx_file/xlsx_memory)
- `path`: xlsx_file: 输出路径(字符串或 {$init_var: <name>})
- `write_defaults`: ref=book_write_defaults; 可选:默认写入语义与冲突策略
- `write_lock`: type=boolean; default=false; xlsx_file: 写锁(默认 false)

#### `book_budget`

- Required: `max_sheets`, `max_total_cells`
- `max_sheets` (required): type=integer; sheet 数量预算(>=1)
- `max_total_cells` (required): type=integer; 总 cell 数预算(>=1)

#### `book_export_xlsx`

- Required: `path`
- `allow_formulas`: type=boolean; default=false; 允许 Excel 公式(可信输入显式 opt-out;默认 false)
- `path` (required): 导出 xlsx 的输出路径(字符串或 {$init_var: <name>})
- `write_lock`: type=boolean; default=false; 写锁(导出时;默认 false)

#### `book_write_defaults`
- `align_by`: type=string; default=field_id; enum=field_id|header; 字段对齐策略(field_id/header;仅 append 生效)
- `header_policy`: type=string; default=once; enum=once|always|never; 表头策略(once/always/never;仅 append 生效)
- `mode`: type=string; default=append; enum=sheet|append; 写入语义(sheet/append)
- `on_conflict`: type=string; default=error; enum=error|overwrite|skip; sheet 冲突策略(error/overwrite/skip;仅 sheet 生效)
- `on_mismatch`: type=string; default=error; enum=error|warn|skip; 字段不匹配策略(error/warn/skip;仅 append 生效)

#### `file`

- Required: `kind`, `path`
- `encoding`: type=string; default=utf-8; csv_file: 文件编码(默认 utf-8)
- `kind` (required): type=string; enum=csv_file; file kind(csv_file)
- `path` (required): csv_file: 输出路径(字符串或 {$init_var: <name>})

#### `resources`
- `books`: type=object; books 资源映射(Excel book; key 为 book_id)
- `files`: type=object; files 资源映射(文件输出资源; key 为 file_id)

## Notes
- 完整字段语义以 `scalim-cli yaml-dsl validate` 的运行时行为为准.
