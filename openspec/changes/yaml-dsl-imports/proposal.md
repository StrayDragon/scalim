## Why

在把一类“批量报表脚本”迁移到 Scalim YAML DSL 时,常见形态是将同一类报表拆成多条事实流的 `demand.yaml`(注册用户/下单/支付订单/purchase 首单等)并在 Python 侧做聚合与多 sheet 输出。

当前拆分后的主要痛点是:
- `sources/relations/fields` 片段在多份 YAML 中大量重复(尤其是 `preload_forever` 的小表与通用 relation),维护成本高且容易不一致。
- YAML anchors/alias 只能在单文件内复用,无法跨文件复用片段,导致“拆分越细,重复越多”。

因此需要一个 **declarative、可 schema validate、fail-fast** 的 YAML 级 `import/include` 机制,让通用片段可跨文件复用,并提供确定性的合并与冲突策略。

## What Changes

- 在 demand YAML 顶层新增 `imports` 映射:声明片段文件别名与路径。
- 在 `sources` / `relations` / 其它 mapping 节点内新增特殊键 `$import`:从 `imports` 引用片段并做确定性合并。
- 固化 import 展开语义:
  - deep-merge + 本地覆盖(叶子冲突本地 wins)
  - 类型不匹配直接报错
  - list 只允许 replace(不做 concat)
  - 支持 `$import` 为 string 或 list,并按顺序合并
  - 检测循环引用与最大展开深度,错误信息包含导入链路
- 不扩展 CLI。仅在 Python 运行入口 `scalim.dsl.by_yaml.run()` / `compile()` 增加可选参数 `path_aliases`:
  - 支持 `"@/..."` 与 `"COMMON:/..."` 风格路径前缀映射到绝对目录,用于解析 import 文件路径与其它 YAML 引用路径
  - 说明: `@/` 形式在 PyYAML 下必须写成字符串(例如 `"@/fragments/x.yaml"`),否则 YAML 语法层无法解析
- 更新 YAML DSL JSON Schema 与语义 validator:
  - schema-only 校验应接受 `imports`/`$import`
  - full validate 在 import 展开后的“最终配置”上执行,保持 fail-fast 与诊断可读
  - 校验错误信息至少包含:
    - 逻辑路径(例如 `sources.orders.fields.order_id`)
    - import 链路(文件路径序列 + `$import` 引用路径),便于定位“错误定义来自哪个片段”

## Notes / Recommendations

- 推荐的片段组织方式(非强制,用于减少重复与口径漂移):
  - `fragments/sources.yaml`: 小表 sources(尤其 `preload_forever`)与通用 params/normalize
  - `fragments/relations.yaml`: 通用 relation chains
  - `fragments/fields.yaml`: 通用字段定义(含命名与 extract/selector)
  - 每个 demand 仅声明 `main_source` + 少量差异项,其它通过 `$import` 引入并做最小覆写
- `$import` 的目标值必须是 mapping,片段文件建议也以“顶层 mapping”作为 SSOT,避免导入 list/scalar 引发歧义。
- 本机制刻意不把 YAML merge(`<<`)作为官方复用路径:
  - YAML merge 在不同解析器/对象身份语义下容易成为 footgun
  - `$import` 的合并/冲突规则可被 schema/validator 解释与诊断,且可以稳定对拍
- 性能建议:
  - import 展开应对“同一路径 + 同一引用”做缓存(同一 demand 编译期避免重复 IO)
  - 递归展开必须有最大深度上限,并在错误中输出链路以定位循环
- 与 workflow 的协同:
  - `path_aliases` 建议作为“跨文件路径解析”的统一能力,供 imports 与 workflow 共同使用,避免两套 alias 规则漂移

## Capabilities

### New Capabilities
- `yaml-dsl-imports`: YAML 级 import/include 复用片段(确定性合并 + 冲突策略 + 循环检测 + 可校验)。

### Modified Capabilities
- (none)

## Impact

- DSL 编译链路: `YamlDemandLoader` 增加 import 展开步骤(在 schema/validator 之前)。
- Public Python API: `scalim.dsl.by_yaml.run/compile` 与 `RunOptions` 增加可选 `path_aliases` 参数。
- Schema/Docs/Tests:
  - schema 生成与漂移门禁需要更新
  - 增加 import 合并、循环检测、路径别名解析的单元/集成测试
  - 文档补充(按 SSOT 规则生成,不手改 `.gen.`)
