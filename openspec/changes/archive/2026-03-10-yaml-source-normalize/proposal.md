## Why

当前仓库内部已经有源级提取器能力,但 YAML 没有稳定入口。当某些 loader 返回 `list[row]`、嵌套 envelope 或其它不直接满足 `key -> row` 读取形状的整体结果时,用户只能为“整理整个返回值形状”再包一层 Python 包装函数。这样不仅重复代码,也会和字段级提取诉求混淆: 有些问题应在 source 级统一 `normalize`,而不是让每个字段各自绕过结果形状。

现在需要给 YAML 增加源级声明式 `normalize`,把整体结果归一化与字段级 `extract` 明确拆开,并为未来的 `normalize_fn` 留出稳定命名空间。

## What Changes

- 在 `sources.<id>` 下新增源级配置 `normalize`,用于声明 lookup source 的 loader 整体返回值在进入字段读取前如何被归一化。
- 初版提供声明式预置,至少覆盖 `kind: index_by_key`,用于把 `list[row]` 一类结果显式归一化为 `lookup_key -> row` 映射,并通过 `key_field` 指定索引键。
- `normalize` 的语义明确为整体结果归一化:
  - 它作用于整个 loader 返回值;
  - 它发生在字段级 `extract` 之前;
  - 它与字段级 `extract` 是两层不同能力,不能互相替代。
- JSON Schema 与编辑器提示必须把这条认知写入 `description` / `markdownDescription`,并至少覆盖:
  - `normalize` 是源级,不是字段级;
  - `index_by_key` 的输入输出形状示例;
  - `normalize` 先于字段 `extract` 执行。
- 初版保持声明式预置,不直接给 YAML 暴露任意 Python normalize 函数;命名与结构应为后续可选的 `normalize_fn` 扩展留出空间,但本变更不引入该能力。

## Capabilities

### New Capabilities
- `yaml-source-normalize`: YAML source 支持声明式 `normalize`,在字段读取前对 loader 整体返回值做整体结果归一化。

### Modified Capabilities
- `demand-dsl`: 扩展 `sources.*` 的 YAML authoring surface,允许声明源级 `normalize`,并定义它与字段级 `extract` 的边界。
- `source-cache`: 明确 preload / cache 语义如何消费 normalize 后的结果形状,确保缓存路径与非缓存路径对字段读取保持一致。
- `yaml-dsl-schema`: 更新 schema 的 `description` / `markdownDescription` / 示例,解释 `normalize` 的源级语义、`index_by_key` 的形状变化以及与字段 `extract` 的区别。
- `yaml-dsl-editor-core`: 编辑器必须跟随 canonical schema 暴露 `normalize` 的补全、hover 与 schema-only 校验结果,确保前端可正确引导源级配置。
- `yaml-dsl-agent-guidance`: 更新 YAML DSL skill 与示例,说明何时使用源级 `normalize`,何时只需要字段级 `extract`。

## Impact

- 影响 source 配置模型、schema 生成、YAML 解析与 source conversion,以及 loader 执行前后的结果归一化链路。
- 影响缓存与 preload 语义,需要明确 normalize 发生的时点以及缓存命中后是否仍观察到同样的归一化结果。
- 需要补充回归测试覆盖 `index_by_key`、冲突 key、缺失 key_field、preload/cache 路径一致性及与字段级 `extract` 的组合使用。
- 需要同步更新文档与示例: `docs/doc/` 下 YAML DSL 文档、迁移说明、整体结果 `normalize` 与字段提取的边界说明。
- 需要同步更新前端编辑器 `frontend/scalim-yaml-dsl-editor/`,确保 schema 镜像、hover、补全与问题面板都能反映源级 `normalize` 新能力。
