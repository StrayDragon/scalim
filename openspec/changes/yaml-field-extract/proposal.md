## Why

当前 YAML DSL 的源字段只能表达“从当前 row 顶层按一个键取值”,当 loader 的单条结果 value 内部是嵌套 dict 或类对象时,用户必须额外写薄 wrapper 先拍平结果,才能继续在 YAML 中声明字段。这把本应属于字段读取层的简单投影抬升成了 Python 代码,也让第 3 点讨论中的 source-level normalize 与 field-level extraction 混在了一起。

现在需要把“单字段如何从当前 row 中取值”单独下沉到 YAML,并明确它与 whole-result normalize 的边界,同时给未来的 `extract_fn` 留出稳定命名空间。

## What Changes

- 在 `main_source.fields.<field_id>` 与 `sources.<id>.fields.<field_id>` 下新增 declarative 字段级配置 `extract`,用于声明当前字段如何从当前 key 对应的 row value 中读取值。
- `extract` 采用点语法(`a.b.c`)表达嵌套读取,且其解析起点明确为“当前 key 对应的 normalized row value”,而不是外层 `loader_result` 映射:
  - 运行时等价起点是主加载路径的 `result[row_id]` 或关联加载路径的 `result[lookup_key]`;
  - 只隐式省略最外层 `lookup_key -> value` 索引包装,不会额外跳过 row value 内部的第一层字段。
- 现有 `field` 继续保留其既有语义: 表示平铺 row 上的直接 data key / 列名,不复用为嵌套路径语义,避免与现有 YAML DSL 认知冲突。
- JSON Schema 与编辑器提示必须把上述边界写入 `description` / `markdownDescription`,并至少覆盖:
  - `extract` 是相对当前 row value 解析,不是相对外层 loader-result mapping;
  - 当 row value 本身再包一层(例如 `payload`)时,该层不得被隐式跳过;
  - `extract` 与 `field` 的使用边界和示例。
- 初版保持 declarative,不在 YAML 中暴露任意 Python extractor;命名与结构应为后续可选的 `extract_fn` 扩展留出空间,但本变更不引入该能力。

## Capabilities

### New Capabilities
- `yaml-field-extract`: YAML 源字段支持 declarative `extract` 路径,从当前 key 对应的 row value 中读取嵌套值。

### Modified Capabilities
- `demand-dsl`: 扩展源字段定义语义,允许在 `main_source.fields.*` / `sources.*.fields.*` 上声明字段级 `extract`,并明确它与现有 `field` 的边界。
- `yaml-dsl-schema`: 更新 schema 的 `description` / `markdownDescription` / 示例,解释 `extract` 的 row-value 相对语义、常见包裹层反例以及与 `field` 的区别。
- `yaml-dsl-editor-core`: 编辑器必须跟随 canonical schema 暴露 `extract` 的补全、hover 与 schema-only 校验结果,确保前端认知与后端 schema 一致。
- `yaml-dsl-agent-guidance`: 更新 YAML DSL skill 与示例,说明何时使用字段级 `extract`,何时应改用 source-level normalize 或保留 Python wrapper。

## Impact

- 影响 YAML DSL 字段模型、parser、validator 与运行时字段读取链路,包括 `dsl/by_yaml/schema_dsl/models/field.py`、相关 schema builder、`config_parsing` 校验逻辑以及 `execution/executor/helpers/field_access.py` 一类的取值路径。
- 需要为主加载与 ref-load 两条执行路径补充一致的语义与回归测试,覆盖 dict/object 嵌套读取、缺失路径、保留平铺 `field` 语义等场景。
- 需要同步更新文档与示例: `docs/doc/` 下 YAML DSL 文档、canonical example、迁移说明与 FAQ。
- 需要同步更新前端编辑器 `frontend/scalim-yaml-dsl-editor/`,确保新字段在 schema 镜像、hover、补全、issues 展示中可见且描述与主仓库一致。
