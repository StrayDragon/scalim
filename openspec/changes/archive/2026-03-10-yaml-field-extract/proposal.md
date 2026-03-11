## Why

当前 YAML DSL 的源字段只能表达“从当前 row 顶层按一个键取值”,当 loader 的单条结果 value 内部是嵌套 dict 或类对象时,用户必须额外写薄包装先拍平结果,才能继续在 YAML 中声明字段。这把本应属于字段读取层的简单投影抬升成了 Python 代码,也让第 3 点讨论中的源级 `normalize` 与字段级提取混在了一起。

现在需要把“单字段如何从当前 row 中取值”单独下沉到 YAML,并明确它与整体结果 `normalize` 的边界,同时给未来的 `extract_fn` 留出稳定命名空间。

## What Changes

- 在 `main_source.fields.<field_id>` 与 `sources.<id>.fields.<field_id>` 下新增声明式字段级配置 `extract`,并将其作为**唯一稳定的字段取值入口**。
- `fields.<field_id>.field` 从稳定 YAML authoring surface 中移除:
  - 需要“顶层 key rename”时,直接使用 `extract: <key_name>`;
  - 历史 `field: ...` 写法在校验阶段 fail-fast,并给出迁移提示。
- `extract` 解释为**相对当前 key 对应的 row value** 的路径表达式,而不是相对外层 `loader_result` 映射:
  - 主加载路径等价起点为 `data = result[row_id]`
  - 关联加载路径等价起点为 `data = result[lookup_key]`
  - 只隐式省略最外层 `lookup_key -> value` 索引包装,不会额外跳过 row value 内部的第一层字段。
- `extract` 语法是“点号 + 方括号”的 path expression(无歧义、无隐式 cast):
  - `a.b.c`: string 段路径(逐段读取 mapping key / obj attr / `__getitem__`)
  - `[1]`: int key 段(用于 `row[1]` 这类非字符串 key)
  - `["a.b"]` / `['a.b']`: string key 段(用于字面量含点号/空格/特殊字符的 key)
  - YAML 书写建议: 为避免与 YAML flow sequence 产生歧义,文档/示例/hover 中应将 `extract` 明确写成字符串,例如 `extract: "[1].x"`、`extract: '["a.b"]'`
  - 系统 MUST NOT 做 `"1" -> 1` 或 `1 -> "1"` 的自动转换,避免歧义
  - 系统 MUST NOT 支持数组下标语义: `[1]` 永远表示“key=1”,不是 list index
- JSON Schema 与编辑器提示必须把上述语义写入 `description` / `markdownDescription`,并至少覆盖:
  - `extract` 的 current-row-relative 解释与常见包裹层反例
  - `extract` 的 bracket 语法(`"[1].x"`、`'["a.b"]'`)与“不做隐式 cast”的说明
  - `field` 已移除,rename 必须用 `extract`
- 初版保持声明式,不在 YAML 中暴露任意 Python extractor;命名与结构应为后续可选的 `extract_fn` 扩展留出空间,但本变更不引入该能力。

## Capabilities

### New Capabilities
- `yaml-field-extract`: YAML 源字段支持 declarative `extract` 路径,从当前 key 对应的 row value 中读取嵌套值。

### Modified Capabilities
- `demand-dsl`: 扩展源字段定义语义: 移除 `field`,以 `extract` 作为唯一字段取值入口,并定义 bracket 语法与 fail-fast 边界。
- `yaml-dsl-schema`: 更新 schema 的 `description` / `markdownDescription` / 示例,解释 `extract` 的 current-row-relative 语义、bracket 语法与迁移提示;并移除 source field `field`。
- `yaml-dsl-editor-core`: 编辑器必须跟随 canonical schema 暴露 `extract` 的补全、hover 与 schema-only 校验结果,确保前端认知与后端 schema 一致。
- `yaml-dsl-agent-guidance`: 更新 YAML DSL skill 与示例,以 `extract` 作为唯一字段取值写法,覆盖 bracket(int/string) 场景并避免继续建议 `field`。

## Impact

- 影响 YAML DSL 字段模型、parser、validator 与运行时字段读取链路,包括 `dsl/by_yaml/schema_dsl/models/field.py`、相关 schema builder、`config_parsing` 校验逻辑以及 `execution/executor/helpers/field_access.py` 一类的取值路径。
- 这是破坏性变更: 仓内所有使用 `fields.*.field` 的 YAML/示例/fixture 必须一次性迁移为 `extract`。
- 需要为主加载与 ref-load 两条执行路径补充一致的语义与回归测试,覆盖 dict/object 嵌套读取、缺失路径、bracket(int/string) key、`["a.b"]` 字面量 key 等场景。
- 需要同步更新文档与示例: `docs/doc/` 下 YAML DSL 文档、canonical example、迁移说明与 FAQ。
- 需要同步更新前端编辑器 `frontend/scalim-yaml-dsl-editor/`,确保新字段在 schema 镜像、hover、补全、issues 展示中可见且描述与主仓库一致。
