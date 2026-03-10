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
DESC_LOADER = "Python 可调用对象引用(支持格式: module.path:ClassName / module.path:obj.method / module.path:function)"
DESC_LOADER_MD = "Python 可调用对象引用.\n\n- `module.path:ClassName`\n- `module.path:function`\n- `module.path:obj.method`"
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
DESC_BIND = "默认绑定(供 steps[].to_bind 缺省时使用); use_keys 默认 as: set, use_rows 默认 cache_mode: batch"
DESC_BIND_MD = (
    "绑定配置(将 rows 或 lookup keys 传给 loader).\n\n"
    "- 必须且只能设置一种: `use_rows` 或 `use_keys`\n"
    "- `param` 为 loader 参数名\n"
    "- 旧写法 `bind: {param: ids}` / `to_bind: {param: ids}` 会被拒绝,请迁移为 `use_keys`/`use_rows`\n"
    "- 若目标 source 未设置 `cache_mode: preload_forever`, 需要 `to_bind` 或 `sources.<id>.bind`"
)
DESC_BIND_PARAM = "下游 loader 参数名(用于传入 lookup keys 或批次行上下文)"
DESC_BIND_AS = "绑定容器: set/list (仅 keys 模式生效)"
DESC_BIND_CACHE_MODE = "rows 模式缓存: batch=批次内复用, none=不复用(仅 rows 模式生效;未配置时默认 batch)"
DESC_BIND_USE_ROWS = "rows 绑定: rows=批次行上下文(主源+已 join)"
DESC_BIND_USE_KEYS = "keys 绑定: keys=lookup keys"
DESC_LOOKUP_CHUNK_SIZE = "keys 模式 LoadRef 的 lookup_keys 分片大小(0/空表示不分片)"
DESC_PARAMS = "调用 loader 时透传的静态参数字典(主源直传,非主源随 bind)"
DESC_PARAMS_MD = (
    "调用 loader 时透传的静态参数字典.\n\n"
    "- main_source.params: 直接以 kwargs 传给 main source loader\n"
    "- sources.<id>.params: 仅在 bind/use_keys 或 bind/use_rows 时合并到 loader kwargs\n"
    "- 当 source 使用 cache_mode: preload_forever 时,预加载调用为无参,不会传 sources.<id>.params"
)
DESC_SOURCE_NORMALIZE = "source-level whole-result `normalize`(在字段级 `extract` 之前对 `loader` 整体返回值整形)"
DESC_SOURCE_NORMALIZE_MD = (
    "source-level whole-result `normalize`.\n\n"
    "- 作用于 `loader` 的整个返回值,用于把整体结果 reshape 成更适合字段读取的形状\n"
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
    "- 若只是 row 内字段嵌套取值,请使用字段级 `extract`"
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
NORMALIZE_KIND_ENUM = ["index_by_key"]
NORMALIZE_ON_CONFLICT_ENUM = ["error", "first", "last"]

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

NORMALIZE_SCHEMA = {
    "type": "object",
    "required": ["kind", "key_field"],
    "properties": {
        "kind": {
            "type": "string",
            "enum": NORMALIZE_KIND_ENUM,
            "description": "normalize 预置类型(index_by_key)",
            "markdownDescription": "normalize 预置类型.\n\n- `index_by_key`: 将 `list[row]` 归一化为 `key -> row` 映射",
            "examples": ["index_by_key"],
        },
        "key_field": {
            "type": "string",
            "description": "用于建立索引的 row 字段名(必填)",
            "markdownDescription": "用于建立索引的 row 字段名(必填).\n\n- 对应 `sources.<id>.key`",
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
    },
    "additionalProperties": False,
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
            "to_bind": BIND_SCHEMA,
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
    "_templates",
    "description",
    "batch_size",
    "retry",
    "main_source",
    "sources",
    "fields",
    "relations",
    "guardrails",
    "output",
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
