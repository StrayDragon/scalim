from typing import Any, Dict

SCHEMA_META_KEY = "schema"
SCHEMA_OMIT_KEY = "schema_omit"


def schema_meta(**kwargs: Any) -> Dict[str, Any]:
    return {SCHEMA_META_KEY: kwargs}


def schema_omit(**kwargs: Any) -> Dict[str, Any]:
    meta: Dict[str, Any] = {SCHEMA_OMIT_KEY: True}
    if kwargs:
        meta[SCHEMA_META_KEY] = kwargs
    return meta


def schema_ref(name: str) -> Dict[str, Any]:
    return {"$ref": "#/definitions/{}".format(name)}


_schema_meta = schema_meta
_schema_omit = schema_omit
_schema_ref = schema_ref


FIELD_KIND_SOURCE = "source"
FIELD_KIND_DERIVED = "derived"
UTF8_ENCODING = "utf-8"
DEFAULT_BATCH_SIZE = 1000
DEFAULT_RELATION_MAX_SAMPLES = 1000
DEFAULT_RELATION_SAMPLING_RATE = 0.01
DEFAULT_PERF_SAMPLING_INTERVAL = 1
DEFAULT_OUTPUT_FORMAT = "csv"
DEFAULT_OUTPUT_ENCODING = UTF8_ENCODING
DEFAULT_OUTPUT_INCLUDE_HEADER = True
DEFAULT_OUTPUT_HEADER_BY = "field_id"
DEFAULT_OUTPUT_STREAMING = True
DEFAULT_CACHE_MODE = "none"
DEFAULT_BIND_AS = "set"
DEFAULT_BIND_CACHE_MODE = "batch"
DEFAULT_NORMALIZE_ON_CONFLICT = "error"
DEFAULT_REL_REPORT_FORMAT = "console"
DEFAULT_PERF_REPORT_FORMAT = "console"
DEFAULT_REL_LOG_TYPE_MISMATCH = True
DEFAULT_GUARDRAILS_MODE = "fast_fail"

DEFAULT_LOADER_RETRY_ENABLED = False
DEFAULT_LOADER_RETRY_MAX_ATTEMPTS = 3
DEFAULT_LOADER_RETRY_MAX_ELAPSED_SECONDS = 10.0
DEFAULT_LOADER_RETRY_BACKOFF = "exponential"
DEFAULT_LOADER_RETRY_BASE_DELAY_SECONDS = 0.2
DEFAULT_LOADER_RETRY_MAX_DELAY_SECONDS = 2.0
DEFAULT_LOADER_RETRY_JITTER = True

HARD_CAP_LOADER_RETRY_MAX_ATTEMPTS = 5
HARD_CAP_LOADER_RETRY_MAX_ELAPSED_SECONDS = 20.0
HARD_CAP_LOADER_RETRY_MAX_DELAY_SECONDS = 5.0

GUARDRAILS_MODE_ENUM = ["quiet", "fast_fail"]
LOADER_RETRY_BACKOFF_ENUM = ["fixed", "exponential"]


DESC_MAIN_SOURCE = "主数据源配置(必填: source_id/loader, 可选 params/order_by)"
DESC_MAIN_SOURCE_MD = (
    "主数据源配置.\n\n"
    "- 必填: `source_id`, `loader`\n"
    "- `source_id` 不能出现在 `sources` 中\n"
    "- `fields` 仅允许源字段(禁止 `compute`)\n"
    "- `order_by` 控制批次内写入顺序(字符串列表,`-` 前缀表示 desc)"
)
DESC_MAIN_SOURCE_ORDER_BY = "主数据源批次内排序字段列表(仅主数据源字段)"
DESC_MAIN_SOURCE_ORDER_BY_MD = (
    "主数据源批次内排序字段列表.\n\n- 每项为字段 id, 前缀 `-` 表示 desc\n- 未配置时保持 loader 原始顺序\n- 仅允许主数据源字段"
)
DESC_LOADER = "Python 可调用对象引用(支持绝对/相对模块引用;支持点式/类式)"
DESC_LOADER_MD = (
    "Python 可调用对象引用.\n\n"
    "绝对引用:\n"
    "- 点式引用: `module.path.function`\n"
    "- 类式引用: `module.path:ClassName` / `module.path:obj.method`\n\n"
    "相对引用:\n"
    "- 以 `.` / `..` 开头的模块路径,相对 YAML 文件所在目录对应的模块路径\n"
    "- 运行期会先归一化为绝对引用,再做白名单校验\n\n"
    "示例:\n"
    "- `.loaders:load_orders`\n"
    "- `.loaders.load_orders`"
)
DESC_LOOKUP_CAST = "归一化 lookup key 的转换(对象结构); sep_first 会先截取首段再做 auto_normalize_key, 例: {name: sep_first, sep: ','}"
DESC_LOOKUP_CAST_MD = (
    "归一化 lookup key 的转换.\n\n"
    "- `name`: auto / int / str / sep_first\n"
    "- `auto` 会拒绝 float lookup key(避免歧义,返回 None 并忽略该键);\n"
    "  若上游可能返回 float(例如 123.0/12.34),请用 `int`/`str` 显式归一化或在 loader 中修复\n"
    "- `sep_first` 先按 `sep` 截取首段再做 normalize"
)
DESC_LOOKUP_CAST_NAME_MD = (
    "转换名称.\n\n- `auto`: 自动归一化\n- `int`: 转为 int\n- `str`: 转为 str\n- `sep_first`: 按 `sep` 截取首段再归一化"
)
DESC_BIND = "Legacy: bind/to_bind (已移除;请使用 params 模板 + `$keys/$rows`)"
DESC_BIND_MD = "Legacy 绑定配置.已从稳定 YAML authoring surface 移除,请使用 `sources.<id>.params` 模板中的 `$keys/$rows` 指令节点."
DESC_BIND_PARAM = "下游 loader 参数名(用于传入 lookup keys 或批次行上下文)"
DESC_BIND_AS = "绑定容器: set/list (仅 keys 模式生效)"
DESC_BIND_CACHE_MODE = "rows 模式缓存: batch=批次内复用, none=不复用(仅 rows 模式生效;未配置时默认 batch)"
DESC_BIND_USE_ROWS = "rows 绑定: rows=批次行上下文(主源+已 join)"
DESC_BIND_USE_KEYS = "keys 绑定: keys=lookup keys"
DESC_LOOKUP_CHUNK_SIZE = "keys 模式 LoadRef 的 lookup_keys 分片大小(0/空表示不分片)"
DESC_PARAMS = "调用 loader 时透传的 kwargs 模板(支持 `{$init_var: <name>}`; sources 支持 `$keys/$rows`)"
DESC_PARAMS_MD = (
    "调用 loader 时透传的 kwargs 模板.\n\n"
    "- `main_source.params`: 直接以 kwargs 传给 main source loader\n"
    "  - 仅允许静态值与 `{$init_var: <name>}` 指令节点(编译期解析为调用方提供的 `init_vars[<name>]`)\n"
    "  - 禁止 `$keys/$rows`\n"
    "- `sources.<id>.params`: loader kwargs 模板(在 ref loader 与 preload 阶段复用)\n"
    "  - 支持 `{$init_var: <name>}` 指令节点(单键映射;inline/block 等价;编译期解析为 `init_vars[<name>]`)\n"
    "  - `$keys`: 注入 lookup keys(支持 nested/list 位置)\n"
    "    - 形式: `{$keys: {as: set|list}}`(默认 set)\n"
    "    - composite key 注入为 tuple 元素\n"
    "  - `$rows`: 注入 batch rows(支持 nested/list 位置)\n"
    "    - 形式: `{$rows: {cache_mode: batch|none}}`(默认 batch)\n"
    "    - 注意: `$rows` 会触发 rows barrier(该层 LoadRef 串行执行)\n"
    "    - 注意: `cache_mode: batch` 会启用批次内复用(减少同 relation 多字段的重复调用);大 batch 下构造 `batch_rows` 可能较重\n"
    "    - 内存提示: 系统不会将完整 `batch_rows` 快照存入长生命周期缓存(避免驻留放大)\n"
    "      若 loader 有副作用或依赖可变 `batch_rows`,请用 `cache_mode: none`\n"
    "- `cache_mode: preload_forever` 的 source:\n"
    "  - 预加载阶段会复用同一份编译后的 `sources.<id>.params` 模板并透传 kwargs\n"
    "  - 禁止 `$keys/$rows`\n\n"
    "迁移:\n"
    "- legacy `bind` / `to_bind` 已移除,请改用 `params` 模板中的 `$keys/$rows` 指令节点\n"
    "- legacy `{$runtime: <name>}` 指令节点已不支持,请改用 `{$init_var: <name>}`\n"
    "- legacy `$runtime.<name>` 字符串占位符已移除,请改用 `{$init_var: <name>}`"
)
DESC_SOURCE_NORMALIZE = "源代码级整体结果 `normalize`(在字段级 `extract` 之前对 `loader` 整体返回值整形)"
DESC_SOURCE_NORMALIZE_MD = (
    "`normalize` 是源代码级的整体结果整形.\n\n"
    "- 作用于 `loader` 的整个返回值,用于把整体结果整理成更适合字段读取的形状\n"
    "- 执行时机: 在字段级 `extract` 之前\n"
    "- 常见用法: 当 `loader` 返回 `list[row]` 时,用 `index_by_key` 归一化为 `key -> row`\n\n"
    "示例:\n"
    "```yaml\n"
    "normalize:\n"
    "  kind: index_by_key\n"
    "  key_field: order_id\n"
    "  on_conflict: error\n"
    "```\n\n"
    "输入/输出形状:\n"
    "- 输入: `[{order_id: 101, ...}, ...]`\n"
    "- 输出: `{101: {order_id: 101, ...}, ...}`\n\n"
    "注意:\n"
    "- 若只是 `row` 内字段嵌套取值,请使用字段级 `extract`"
)
DESC_FIELD_NAME = "字段显示名称"
DESC_FIELD_NAME_MD = "字段显示名称.\n\n- `output.header_fields_output_by: name` 时作为表头"
DESC_RELATION_STEPS = (
    "按顺序定义等值关联链(from == to),系统不会重排 steps,"
    " 表示从 main_source 出发沿链路到达当前字段 source"
    " (例: steps: [{from: orders.customer_id, to: customers.customer_id}])"
)
DESC_RELATION_STEPS_MD = (
    "按顺序定义等值关联链(from == to).\n\n"
    "- `from`/`to` 支持 `source.field` 或列表\n"
    "- `field` 必须是字段的 `field_id`(YAML key),或 `sources.<id>.key` 中声明的 key 字段(不允许写 loader data_key)\n"
    "- 列表用于复合键, 长度需一致\n"
    "- 链路必须连续: steps[n].from 的 source = steps[n-1].to 的 source"
)
OUTPUT_FIELD_ID_KEY = "field_id"
OUTPUT_FIELD_SOURCE_KEY = "source"
OUTPUT_FIELD_DATA_KEY_KEY = "field"

DESC_OBSERVABILITY = "可观测性配置"
DESC_OBSERVABILITY_MD = "可观测性配置.\n\n包含 `logging`、`performance`、`relations`、`viz`、`trace`、`row_gap` 与 `memory_opt` 子配置."
LOOKUP_CAST_NAME_ENUM = ["auto", "int", "str", "sep_first"]
BIND_AS_ENUM = ["set", "list"]
BIND_CACHE_MODE_ENUM = ["none", "batch"]
VALUE_CAST_ENUM = ["auto", "int", "str"]
NORMALIZE_KIND_ENUM = ["index_by_key", "take_first", "project_fields", "map_values"]
NORMALIZE_ON_CONFLICT_ENUM = ["error", "first", "last"]
NORMALIZE_ON_EMPTY_ENUM = ["miss", "null", "error"]
NORMALIZE_ON_MISSING_ENUM = ["error", "null"]

DESC_LOADER_RETRY = "Loader retry 策略(可选;默认关闭)"
DESC_LOADER_RETRY_MD = (
    "Loader retry 策略.\n\n"
    "- 默认关闭: `enabled: false`\n"
    "- 启用后会对 loader 调用的瞬态错误做有限重试\n"
    "- 需要提供 `should_retry` 回调(安全引用),用于决定是否重试\n"
    "- 受硬上限保护: max_attempts<=5, max_elapsed_seconds<=20, max_delay_seconds<=5\n"
)


_SOURCE_ID_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
_SOURCE_FIELD_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$"
SOURCE_ID_STRING_SCHEMA = {
    "type": "string",
    "pattern": _SOURCE_ID_PATTERN,
    "description": "格式: source_id (字母/数字/下划线, 首字符为字母或下划线)",
    "markdownDescription": "格式: `source_id`.\n\n- 仅允许字母/数字/下划线\n- 首字符必须是字母或下划线",
}

_SOURCE_ID_STRING_SCHEMA = SOURCE_ID_STRING_SCHEMA
FIELD_ID_STRING_SCHEMA = {
    "type": "string",
    "pattern": _SOURCE_ID_PATTERN,
    "description": "格式: field_id (字母/数字/下划线, 首字符为字母或下划线)",
    "markdownDescription": "格式: `field_id`.\n\n- 仅允许字母/数字/下划线\n- 首字符必须是字母或下划线",
}
_SOURCE_FIELD_STRING_SCHEMA = {
    "type": "string",
    "pattern": _SOURCE_FIELD_PATTERN,
    "description": "格式: source.field (source 与 field 使用同样命名规则)",
    "markdownDescription": (
        "格式: `source.field`.\n\n"
        "- 仅允许字母/数字/下划线\n"
        "- `field` 必须是字段的 `field_id`(YAML key)\n"
        "- 不允许写 loader 的 data_key; 若 field_id != data_key,仍必须在 steps 中写 field_id\n"
        "- 对于非主源的 key 字段,也可直接引用 `sources.<id>.key` 中声明的字段名\n"
        "- 系统会将 `field_id` 映射为其 `field`(data_key)"
    ),
}
SOURCE_FIELD_ID_STRING_SCHEMA = {
    "type": "string",
    "pattern": _SOURCE_FIELD_PATTERN,
    "description": "格式: source.field_id (两段式,单个 '.' 分隔)",
    "markdownDescription": (
        "格式: `source.field_id`.\n\n"
        "- 仅允许两段式(单个 `.` 分隔)\n"
        "- `field_id` 必须是字段的 `field_id`(YAML key)\n"
        "- 用于 `output.fields` 显式消歧: 当 field_id 在多个 source 中同名时,用 `source.field_id` 选择"
    ),
}
_SOURCE_FIELD_LIST_SCHEMA = {
    "type": "array",
    "items": _SOURCE_FIELD_STRING_SCHEMA,
    "minItems": 1,
}

RELATION_STEP_FROM_SCHEMA = {
    "oneOf": [_SOURCE_FIELD_STRING_SCHEMA, _SOURCE_FIELD_LIST_SCHEMA],
    "description": "上游字段(等值条件左侧),格式 source.field; 多字段用列表",
    "markdownDescription": (
        "上游字段(等值条件左侧).\n\n"
        "- `source.field` 或列表\n"
        "- `field` 必须是字段的 `field_id`(YAML key),不允许写 loader data_key\n"
        "- 列表用于复合键, 长度需与 `to` 对齐\n"
        "- 同一侧必须来自同一 source"
        "\n\n常见错误:\n"
        "- ❌ 写 data_key: `products.category_id`\n"
        "- ✅ 写 field_id: `products.product_category_id` (schema 会映射到 data_key)"
    ),
    "examples": ["orders.customer_id", ["orders.region_id", "orders.institution_id"]],
}
RELATION_STEP_TO_SCHEMA = {
    "oneOf": [_SOURCE_FIELD_STRING_SCHEMA, _SOURCE_FIELD_LIST_SCHEMA],
    "description": "下游字段(等值条件右侧/lookup key),格式 source.field; 多字段用列表",
    "markdownDescription": (
        "下游字段(等值条件右侧/lookup key).\n\n"
        "- `source.field` 或列表\n"
        "- `field` 必须是字段的 `field_id`(YAML key),不允许写 loader data_key\n"
        "- 列表用于复合键, 长度需与 `from` 对齐\n"
        "- 同一侧必须来自同一 source"
        "\n\n常见错误:\n"
        "- ❌ 写 data_key: `products.category_id`\n"
        "- ✅ 写 field_id: `products.product_category_id` (schema 会映射到 data_key)"
    ),
    "examples": ["customers.customer_id", ["regions.region_id", "mappings.institution_id"]],
}

LOOKUP_CAST_SCHEMA = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {
            "type": "string",
            "enum": LOOKUP_CAST_NAME_ENUM,
            "description": "转换名称(auto/int/str/sep_first)",
            "markdownDescription": DESC_LOOKUP_CAST_NAME_MD,
            "examples": ["auto"],
        },
        "sep": {
            "type": "string",
            "description": "sep_first 的分隔符(默认 ,)",
        },
    },
    "additionalProperties": False,
    "description": DESC_LOOKUP_CAST,
    "markdownDescription": DESC_LOOKUP_CAST_MD,
}

_DESC_SOURCE_NORMALIZE_KIND_MD = (
    "normalize 预置类型.\n\n"
    "- `index_by_key`: 将 `list[row]` 归一化为 `key -> row` 映射\n"
    "- `take_first`: 将 `mapping[key -> list[row]]` 归一化为 `mapping[key -> row]`(空列表由 `on_empty` 决定)\n"
    "- `project_fields`: 对 `mapping[key -> row]` 的 row value 做投影/重命名(支持 int-key path,可注入 `from_key`)\n"
    "- `map_values`: 对 `mapping` 的 values 批量应用 normalize steps(例如 take_first + project_fields)\n\n"
    "注意:\n"
    "- 顶层 `list[row]` 场景请用 `index_by_key`(通过 `on_conflict` 定义冲突策略)\n"
    "- `call_by` 为受控扩展点: whole-result `Mapping -> Mapping`(受 allowlist 约束)"
)

_DESC_SOURCE_NORMALIZE_CALL_BY_MD = (
    "Normalize 受控扩展点(可选).\n\n"
    "- 形式与 `loader` 引用一致(支持绝对/相对引用)\n"
    "- 相对引用会在运行期先归一化为绝对引用,再做 allowlist 校验\n"
    "- 固定 contract: 输入与输出均为 `Mapping`\n\n"
    "建议签名:\n"
    "- `fn(result, ctx) -> Mapping`\n"
    "  - `ctx.source_id`\n"
    "  - `ctx.kind`\n"
    "  - `ctx.config_path`"
)

_NORMALIZE_PROJECT_FIELD_RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "from_key": {
            "type": "boolean",
            "description": "将 lookup key 写入该字段",
            "markdownDescription": "将 lookup key(外层 mapping 的 key)写入该字段.\n\n- true: 注入\n- false: 不注入",
            "examples": [True],
        },
        "extract": {
            "type": "string",
            "minLength": 1,
            "description": "从当前 row value 提取字段值的路径表达式",
            "markdownDescription": (
                "从当前 key 对应的 row value 中提取字段值的路径表达式.\n\n"
                "- 语法与字段级 `extract` 一致: dot + bracket path\n"
                '- 支持 int-key: `"[1].x"`(表示 key=1,不是数组下标)\n'
                "- 缺失/路径不匹配时为 missing(由 `on_missing` 决定)"
            ),
            "examples": ["review_status", "[1].clearn_reason_level"],
        },
    },
    "additionalProperties": False,
    "allOf": [
        {
            "oneOf": [
                {"required": ["from_key"], "not": {"required": ["extract"]}},
                {"required": ["extract"], "not": {"required": ["from_key"]}},
            ]
        }
    ],
}

_NORMALIZE_PROJECT_FIELDS_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "description": "投影字段映射(key 为输出字段名)",
    "markdownDescription": (
        "投影字段映射.\n\n"
        "- key: 输出字段名(天然完成 rename)\n"
        "- value: 投影规则(`from_key` 或 `extract` 二选一)\n"
        '- `extract` 支持 int-key path(例如 `"[1].x"`)'
    ),
    "propertyNames": {"type": "string", "pattern": _SOURCE_ID_PATTERN},
    "additionalProperties": _NORMALIZE_PROJECT_FIELD_RULE_SCHEMA,
}

_NORMALIZE_STEP_KIND_ENUM = ["take_first", "project_fields"]

_NORMALIZE_STEP_SCHEMA = {
    "type": "object",
    "required": ["kind"],
    "properties": {
        "kind": {
            "type": "string",
            "enum": _NORMALIZE_STEP_KIND_ENUM,
            "description": "normalize step 类型(take_first/project_fields)",
            "markdownDescription": "normalize step 类型.\n\n- `take_first`\n- `project_fields`",
            "examples": ["take_first"],
        },
        "on_empty": {
            "type": "string",
            "enum": NORMALIZE_ON_EMPTY_ENUM,
            "default": "miss",
            "description": "空列表策略(miss/null/error)",
            "markdownDescription": (
                "空列表策略.\n\n- `miss`: 该 key 视为 lookup miss(从结果映射中移除)\n- `null`: 写入 `None`\n- `error`: 抛错"
            ),
            "examples": ["miss"],
        },
        "on_missing": {
            "type": "string",
            "enum": NORMALIZE_ON_MISSING_ENUM,
            "default": "error",
            "description": "缺失路径策略(error/null)",
            "markdownDescription": "缺失路径策略.\n\n- `error`: 抛错(默认)\n- `null`: 缺失则填 `None`",
            "examples": ["error"],
        },
        "fields": _NORMALIZE_PROJECT_FIELDS_SCHEMA,
    },
    "additionalProperties": False,
    "allOf": [
        {
            "oneOf": [
                {
                    "required": ["kind"],
                    "properties": {"kind": {"enum": ["take_first"]}},
                    "not": {"anyOf": [{"required": ["on_missing"]}, {"required": ["fields"]}]},
                },
                {
                    "required": ["kind", "fields"],
                    "properties": {"kind": {"enum": ["project_fields"]}},
                    "not": {"anyOf": [{"required": ["on_empty"]}]},
                },
            ]
        }
    ],
}

_NORMALIZE_STEPS_SCHEMA = {
    "type": "array",
    "items": _NORMALIZE_STEP_SCHEMA,
    "minItems": 1,
    "description": "按顺序执行的 normalize steps",
    "markdownDescription": "按顺序执行的 normalize steps.\n\n- 对每个 `(key, value)` 依次执行",
}

NORMALIZE_SCHEMA = {
    "type": "object",
    "required": ["kind"],
    "properties": {
        "kind": {
            "type": "string",
            "enum": NORMALIZE_KIND_ENUM,
            "description": "normalize 预置类型",
            "markdownDescription": _DESC_SOURCE_NORMALIZE_KIND_MD,
            "examples": ["index_by_key", "take_first", "project_fields", "map_values"],
        },
        "key_field": {
            "type": "string",
            "description": "用于建立索引的 row 字段名(index_by_key)",
            "markdownDescription": "用于建立索引的 row 字段名.\n\n- 仅 `kind: index_by_key` 使用\n- 对应 `sources.<id>.key`",
            "examples": ["order_id"],
        },
        "on_conflict": {
            "type": "string",
            "enum": NORMALIZE_ON_CONFLICT_ENUM,
            "default": DEFAULT_NORMALIZE_ON_CONFLICT,
            "description": "duplicate key 冲突策略(error/first/last)",
            "markdownDescription": "duplicate key 冲突策略.\n\n- `error`: 报错(默认)\n- `first`: 保留第一条\n- `last`: 保留最后一条",
            "examples": ["error"],
        },
        "on_empty": {
            "type": "string",
            "enum": NORMALIZE_ON_EMPTY_ENUM,
            "default": "miss",
            "description": "空列表策略(miss/null/error)",
            "markdownDescription": (
                "空列表策略.\n\n- `miss`: 该 key 视为 lookup miss(从结果映射中移除)\n- `null`: 写入 `None`\n- `error`: 抛错"
            ),
            "examples": ["miss"],
        },
        "on_missing": {
            "type": "string",
            "enum": NORMALIZE_ON_MISSING_ENUM,
            "default": "error",
            "description": "缺失路径策略(error/null)",
            "markdownDescription": "缺失路径策略.\n\n- `error`: 抛错(默认)\n- `null`: 缺失则填 `None`",
            "examples": ["error"],
        },
        "fields": _NORMALIZE_PROJECT_FIELDS_SCHEMA,
        "steps": _NORMALIZE_STEPS_SCHEMA,
        "call_by": {
            "type": "string",
            "description": "Normalize 受控扩展点(安全引用,由 allowlist 约束)",
            "markdownDescription": _DESC_SOURCE_NORMALIZE_CALL_BY_MD,
            "examples": ["myapp.normalizes:normalize_source_x"],
        },
    },
    "additionalProperties": False,
    "allOf": [
        {
            "oneOf": [
                {
                    "required": ["kind", "key_field"],
                    "properties": {"kind": {"enum": ["index_by_key"]}},
                    "not": {
                        "anyOf": [
                            {"required": ["on_empty"]},
                            {"required": ["on_missing"]},
                            {"required": ["fields"]},
                            {"required": ["steps"]},
                        ]
                    },
                },
                {
                    "required": ["kind"],
                    "properties": {"kind": {"enum": ["take_first"]}},
                    "not": {
                        "anyOf": [
                            {"required": ["key_field"]},
                            {"required": ["on_conflict"]},
                            {"required": ["on_missing"]},
                            {"required": ["fields"]},
                            {"required": ["steps"]},
                        ]
                    },
                },
                {
                    "required": ["kind", "fields"],
                    "properties": {"kind": {"enum": ["project_fields"]}},
                    "not": {
                        "anyOf": [
                            {"required": ["key_field"]},
                            {"required": ["on_conflict"]},
                            {"required": ["on_empty"]},
                            {"required": ["steps"]},
                        ]
                    },
                },
                {
                    "required": ["kind", "steps"],
                    "properties": {"kind": {"enum": ["map_values"]}},
                    "not": {
                        "anyOf": [
                            {"required": ["key_field"]},
                            {"required": ["on_conflict"]},
                            {"required": ["on_empty"]},
                            {"required": ["on_missing"]},
                            {"required": ["fields"]},
                        ]
                    },
                },
            ]
        }
    ],
    "description": DESC_SOURCE_NORMALIZE,
    "markdownDescription": DESC_SOURCE_NORMALIZE_MD,
}

LOOKUP_CHUNK_SIZE_SCHEMA = {
    "oneOf": [
        {"type": "integer", "minimum": 0},
        {"type": "null"},
    ],
    "description": DESC_LOOKUP_CHUNK_SIZE,
    "markdownDescription": "keys 模式 lookup_keys 分片大小.\n\n- `0` / `null` 表示不分片",
}

BIND_ROWS_SCHEMA = {
    "type": "object",
    "required": ["param"],
    "properties": {
        "param": {"type": "string", "description": DESC_BIND_PARAM},
        "cache_mode": {
            "type": "string",
            "enum": BIND_CACHE_MODE_ENUM,
            "default": DEFAULT_BIND_CACHE_MODE,
            "description": DESC_BIND_CACHE_MODE,
            "markdownDescription": "rows 缓存策略.\n\n- `batch`: 批次内复用\n- `none`: 不复用",
            "examples": ["batch"],
        },
    },
    "additionalProperties": False,
    "description": DESC_BIND_USE_ROWS,
    "markdownDescription": ("rows 绑定: 传入批次行上下文(主源 + 已 join).\n\n- `param` 必填\n- `cache_mode`: batch/none"),
}

BIND_KEYS_SCHEMA = {
    "type": "object",
    "required": ["param"],
    "properties": {
        "param": {"type": "string", "description": DESC_BIND_PARAM},
        "as": {
            "type": "string",
            "enum": BIND_AS_ENUM,
            "default": DEFAULT_BIND_AS,
            "description": DESC_BIND_AS,
            "markdownDescription": "keys 容器类型.\n\n- `set`: 去重\n- `list`: 保持顺序",
            "examples": ["set"],
        },
    },
    "additionalProperties": False,
    "description": DESC_BIND_USE_KEYS,
    "markdownDescription": "keys 绑定: 传入 lookup keys.\n\n- `param` 必填\n- `as`: set/list",
}

BIND_SCHEMA = {
    "oneOf": [
        {
            "type": "object",
            "required": ["use_rows"],
            "properties": {"use_rows": BIND_ROWS_SCHEMA},
            "additionalProperties": False,
        },
        {
            "type": "object",
            "required": ["use_keys"],
            "properties": {"use_keys": BIND_KEYS_SCHEMA},
            "additionalProperties": False,
        },
    ],
    "description": DESC_BIND,
    "markdownDescription": DESC_BIND_MD,
}

RELATION_STEPS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["from", "to"],
        "properties": {
            "from": RELATION_STEP_FROM_SCHEMA,
            "to": RELATION_STEP_TO_SCHEMA,
            "lookup_cast": LOOKUP_CAST_SCHEMA,
        },
        "additionalProperties": False,
    },
    "minItems": 1,
    "description": DESC_RELATION_STEPS,
    "markdownDescription": DESC_RELATION_STEPS_MD,
}

DEMAND_SCHEMA_META = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://scalim.example.com/schemas/demand.json",
    "title": "Scalim 需求配置",
    "description": "Scalim 框架 YAML 需求配置定义 Schema",
    "markdownDescription": (
        "Scalim 框架 YAML 需求配置定义 Schema.\n\n"
        "入口字段: `main_source` / `sources` / `fields`.\n"
        "不再支持 legacy 字段: relations_sql_like / relations_graph / foreign_key / target / from / via / "
        "column / pk / pk_transform / derived."
    ),
}
DEMAND_SCHEMA_REQUIRED = ["name", "main_source"]
DEMAND_SCHEMA_PROPERTIES_ORDER = [
    "name",
    "imports",
    "$import",
    "_templates",
    "description",
    "batch_size",
    "retry",
    "main_source",
    "sources",
    "fields",
    "relations",
    "guardrails",
    "outputs",
    "failure_policy",
    "include_full_error_message",
    "meta",
    "audit",
    "observability",
]
FIELD_DERIVED_CONDITIONS = [
    {
        "oneOf": [
            {"required": ["compute"], "not": {"required": ["call_by"]}},
            {"required": ["call_by"], "not": {"required": ["compute"]}},
        ]
    }
]
DEMAND_FIELDS_KEY = "fields"
