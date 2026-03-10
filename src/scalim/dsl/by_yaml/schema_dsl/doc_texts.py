from typing import List


def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


# NOTE:
# - `YAML DSL` 的用户可见描述(尤其是 `schema` 的 `markdownDescription`)尽量只维护一份.
# - 文档站点中的对应片段可以在 `just gen` 阶段从这里同步生成.
#
# 约定:
# - 第一行用作 `JSON Schema` 的 `description`(纯文本),其余部分用于 `markdownDescription`.
SOURCE_FIELD_EXTRACT_MD = """\
从当前 key 对应的 row value 中提取字段值的路径表达式(不是相对整个 loader-result mapping).

语法: dot + bracket path(建议写成字符串,避免 YAML 歧义):
- `extract` 省略时,等价于 `extract: <field_id>`(顶层同名 key)
- dot: `a.b.c`
- int-key: `"[1].clearn_reason_level"` (表示 key=1,不是 list index)
- 字面量 string key: `'["a.b"].x'` (用于 key 本身包含点号等特殊字符)

注意:
- 不做 `"1"` ↔ `1` 的隐式转换(避免歧义)
- 不支持数组/列表下标语义: `[1]` 永远表示 “key=1”
- 缺失/路径不匹配时返回 `None`

示例(含嵌套取值):

```yaml
main_source:
  fields:
    # 顶层同名 key: extract 可省略
    review_status:
      name: 审核状态

    # int-key nested dict: role_id 是 int(例如 1/2)
    customer_clearn_reason_level:
      name: 客户净利原因等级
      extract: "[1].clearn_reason_level"

    # dotted literal key: row 的 key 就叫 "a.b"
    dotted_literal_key_value:
      extract: '["a.b"].x'
```

示例(给定 loader 返回值,extract 提取后的输出长什么样):

```python
result = {
  1: {1: {"clearn_reason_level": 2}, 2: {"clearn_reason_level": 1}, "review_status": 0},
}
```

字段:

```yaml
sources:
  clearn_reasons:
    fields:
      customer_level:
        extract: "[1].clearn_reason_level"
      operation_level:
        extract: "[2].clearn_reason_level"
      review_status:
        extract: review_status
```

对 `lookup_key=1` 的 row value:
- `customer_level` → `2`
- `operation_level` → `1`
- `review_status` → `0`

最终输出行片段:

```python
{"customer_level": 2, "operation_level": 1, "review_status": 0}
```

补充边界:
- 如果中间段是 list/tuple, `"[1]"` 也不会当作下标(会返回 `None`)
- 如果同时存在 key `"1"` 与 `1`,需要用 `extract: '["1"].x'` 与 `extract: "[1].x"` 明确区分
"""

SOURCE_FIELD_EXTRACT_DESC = _first_non_empty_line(SOURCE_FIELD_EXTRACT_MD)


def build_generated_doc_block(lines: List[str]) -> str:
    """生成写入到 `Markdown` 文档中的块(不包含 `marker` 本身)."""

    if not lines:
        return ""
    # 保证输出以 `\\n` 结尾,避免无意义 `diff` 漂移.
    return "\n".join(lines).rstrip() + "\n"
