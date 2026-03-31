## Why

`outputs_defaults` 当前只承载 `outputs_defaults.to.book` 这一处默认值,但却引入了一个“空的顶层 defaults 容器”概念,对作者不直观、对读者不友好,并且给未来的输出目的地扩展带来结构负担(默认值会继续堆在一个语义弱的桶里).

同时,该默认值与运行期 `overrides.outputs_defaults` 的 patch/overlay 分支,让 IO 绑定路径出现了第三种入口(除 `resources`/`outputs` 之外),增加实现/测试/文档维护成本。

## What Changes

- **BREAKING**: 移除 demand YAML 顶层字段 `outputs_defaults`(不再允许声明 `outputs_defaults.to.book`).
- **BREAKING**: 移除 Excel 输出对 `outputs_defaults.to.book` 的继承逻辑; Excel 输出必须显式提供 `outputs[*].to.book`.
- **BREAKING**: 移除 by_yaml runtime 的 `RunOverrides.outputs_defaults` 以及 workflow 编译侧对 `overrides.outputs_defaults` 的支持.
- 更新校验错误信息与迁移提示,引导用户用 YAML anchors(`_templates`) 或 `$import` 片段在 `outputs[*].to` 处复用 `book` 绑定,而不是依赖全局默认值.
- 同步更新相关 OpenSpec specs 与用户文档(含 schema 参考与示例).

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `yaml-dsl-books-resources`: 移除 `outputs_defaults.to.book` 绑定入口与继承规则;要求 `outputs[*].to.book` 显式声明,并更新 fail-fast 诊断路径与迁移提示.
- `yaml-dsl-output-overrides`: 移除 IO-only `overrides.outputs_defaults` 覆盖能力;保留 `overrides.outputs`(replace) 与 `overrides.resources`(overlay) 作为运行期改写入口.
- `yaml-dsl-workflow-validate`: 更新 workflow 校验场景与诊断路径,不再引用 `outputs_defaults.to.book`.
- `workflow-sheetbook-resources`: 更新对 demand outputs 绑定面的引用,不再包含 `outputs_defaults`.
- `workflow-shared-output-containers`: 更新写入节点推导的输入字段集合,不再读取 `outputs_defaults`.
- `skill-docs-write-to-cleanup`: 更新文档/规范中对 demand 输出绑定面的表述,不再包含 `outputs_defaults`.

## Impact

- **YAML authoring**: 现有依赖 `outputs_defaults.to.book` 的 demand 需要迁移为在每个 Excel output 上声明 `to.book`,并用 anchors/`$import` 做复用.
- **Public API**: `RunOverrides.outputs_defaults` 删除;调用侧若需要改写输出绑定,应通过 `overrides.outputs`(replace) 显式提供 outputs 列表,或通过 `overrides.resources.books` 覆盖 book 的 path/export/budget 等 IO 配置.
- **Runtime / Workflow**: output composition 与 workflow write-node 推导逻辑将简化(仅从 `outputs[*].to.book` 读取).
- **Docs & schema**: `demand.gen.json`、schema reference 与示例需同步更新;生成物遵循 docs governance(通过既有生成入口刷新,不手改 `.gen.*`).

