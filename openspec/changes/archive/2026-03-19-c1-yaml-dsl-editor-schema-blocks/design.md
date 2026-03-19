## Context

当前 `frontend/scalim-yaml-dsl-editor` 的 Visual 编辑面板同时承担了两类职责:

1) **schema → UI**: 把 canonical JSON Schema（`src/schema/demand.gen.json` 等）映射为可视化编辑控件与布局
2) **UI → patch**: 把用户交互转为 YAML patch 并走既有 decision UX（alias/merge key 等边界）

随着 YAML DSL schema 演进,手写面板与（或）schema-form 依赖的维护成本与升级风险逐渐成为瓶颈:

- 面板数量多且逻辑分散,同一路径的“可编辑/不可编辑”边界难以保持一致
- 外部 schema-form 往往绑定 Svelte 主版本与生态,会把升级风险扩散到整个编辑器
- 对 anyOf/oneOf 等复杂 schema,纯表单渲染难以同时满足可用性与 roundtrip 稳定性

本设计通过引入内部 `schema_blocks` 子模块,将 schema-driven 的“可编辑块”抽象出来,并把写回动作收敛为可组合的标准 action,最终统一映射到现有 YAML patch 能力,以保持 roundtrip 稳定与交互一致性。

约束与边界:

- 本变更仅修改 `frontend/scalim-yaml-dsl-editor/**`。
- canonical schema（例如 `frontend/scalim-yaml-dsl-editor/src/schema/demand.gen.json`）属于生成物,本变更不手改与不更改其生成流程。
- 结构化编辑写回固定走 `yaml_patch.ts` + `yaml_edit_ops.ts`（不做对象序列化覆写）。

## Goals / Non-Goals

**Goals:**

- 提供内部模块 `src/libs/schema_blocks/` 将 JSON Schema 稳定地转换为 `EditableBlock[]`,并可被 UI 与自定义扩展复用。
- 标准化写回抽象 `BlockAction` → `YamlEditOp` → `applyYamlEditOp`,复用现有 safe/rewrite + decision（AliasDecisionModal/PatchPreviewModal）交互链路。
- 通过 OverrideRegistry 支持按 YAML path 注册手写嵌入点,以承接关系链图、派生依赖、输出字段候选/别名/锚点解析等强交互模块。
- 对 anyOf/oneOf 提供“可推断分支”的最小 selector;不可推断时提供明确 fallback（标记 unsupported + 跳转 raw YAML）。
- UI 侧提供 schema-driven 面板（新增 `SchemaBlocksPanel.svelte` 或等价入口）,在运行时替换/覆盖现有大部分手写面板,但允许分阶段迁移与回滚。

**Non-Goals:**

- 不引入第三方 schema-form 库（包括需要更高 Svelte 版本的方案）。
- v1 不提供通用 rename（如 map key rename）；复杂迁移由 custom block 以“删除+新建+迁移”策略显式实现。
- 不试图在 v1 覆盖所有 JSON Schema 边界（复杂 union/深度 patternProperties/高度动态结构）;遇到不可表达场景统一回退 raw YAML。
- 不触碰 `frontend/scalim-viz/**` 与其它在途前端变更。

## Decisions

### 1) 采用“Editable Blocks”作为 schema-driven UI 的稳定中间层

在 `schema_blocks` 内部把 schema 展开为一组可渲染的块（`EditableBlock`）而不是直接渲染表单,原因:

- UI 渲染层可以保持轻量,只依赖 block 的 `kind/ui/children/actions` 等稳定字段
- 便于对强交互区域做 custom blocks（`kind: "custom"`）并通过 overrides 替换默认生成
- 便于单测: `buildBlocks(...)` 可在纯 TS 层做快照式验证,而不依赖 DOM

关键约定:

- `EditableBlock.id` 稳定且可预测,默认由 `yamlPath.join(".")` 生成（数组索引使用 `"0"` 等字符串）
- `yamlPath` 是写回的唯一 SSOT（UI 不保留单独的“对象模型”）

### 2) 写回动作统一建模为 BlockAction,并映射到既有 patch 能力

每个 block 暴露标准 actions（`setScalar/deletePath/ensureMap/ensureSeq/insertSeqItem/removeSeqItem/moveSeqItem` 等）。
UI 层触发 action 后:

1) action → `YamlEditOp`
2) `applyYamlEditOp(...)` 返回 patch plan:
   - `plan.kind === "safe"`: 直接更新 `state.yamlText`
   - `plan.kind === "rewrite"` 且带 decision: 复用现有 Modal 处理路径（alias/merge key 等）

这样做的好处:

- roundtrip 与 alias 语义由既有链路兜底,避免在 schema-driven 层“偷偷序列化”
- patch decision UX 不分裂: schema-driven 与旧面板保持一致交互心智

### 3) OverrideRegistry 以 YAML path pattern 为扩展点（精确>glob>默认）

Override 机制以 YAML path 为 anchor,避免“按 schema 结构”扩展导致漂移:

- match 规则:
  1. 精确 path 匹配 > glob 匹配 > schema 默认生成
  2. priority 高覆盖低
  3. 覆盖命中后默认不生成该节点 children（除非 custom builder 主动组合 `buildBlocks`）

这样既能保留 schema-driven 的自动覆盖面,又能把复杂交互集中在少数 custom blocks 上,降低长期维护成本。

### 4) anyOf/oneOf 仅做“可推断分支”的 union selector,否则一律 fallback

v1 的 union 策略以可预测为第一优先级:

- 若分支存在明确 discriminator（如 const 字段、或唯一 required key 集合）→ 生成 `kind: "union"` block + selector
- 否则标记为 `kind: "unsupported"` 并渲染为“提示 + 跳转 raw YAML”

避免在不可推断 union 上做“猜测式 UI”,从而产生错误写回或不可解释的重写。

### 5) UI 集成采用“新增面板 + 逐步迁移”而非一次性重写

为降低回归风险,优先新增 `SchemaBlocksPanel.svelte` 并在面板选择入口中替换默认入口（或在 feature flag 下可切换）。

迁移策略:

- 先覆盖 schema-driven 可表达的字段与常见结构（scalar/enum/object/array/map）
- 对强交互区域先做 override/custom block 嵌入（relations/derived deps/output fields 等）
- 当 schema-driven 面板达到可用 parity 后,再逐步移除旧面板实现或降级为 custom block 的容器

## Risks / Trade-offs

- [Schema 解析复杂度] `$ref`/allOf/union 展开可能引入边界 bug → v1 限制支持面,无法推断的 union 统一 fallback raw YAML;并为 buildBlocks 补齐单测覆盖常见结构。
- [Block id/顺序稳定性] schema 属性排序变化可能导致 UI 重排 → block 生成规则固定（required 置顶 + 其余字母序/显式 order）,并在单测中断言输出顺序与 id 稳定。
- [性能] 每次 YAML 变更都重建 blocks 可能卡顿 → UI 层按需 rebuild（schema 变更/解析结果变更时）并做 memoization（按 root schema + yamlPath + overrides key）。
- [回归风险] 替换现有面板可能破坏熟悉流程 → 引入可切换入口（或保留旧 VisualPanel 作为回退）,并优先复用现有 patch decision UX。
- [Map 编辑复杂度] additionalProperties/patternProperties 的 key/value 编辑易引发重写 → v1 限制 map value 形态（scalar/object 常见形态）;其余回退 raw YAML。

## Migration Plan

1. 新增 `src/libs/schema_blocks/`（模型/解析/生成/override registry/action 映射）与单测。
2. 新增 schema-driven 面板 `SchemaBlocksPanel.svelte`,对接现有 YAML state 与 patch decision 交互。
3. 为强交互区域提供 overrides/custom blocks 的落点,把旧面板的核心交互组件逐步拆为可复用 custom blocks。
4. 在 `public/examples/*.yaml` 上做手工验收: 创建缺失 section、编辑 enum、编辑数组 items、触发 alias decision、跳转 raw YAML。
5. 若 schema-driven 面板达到 parity,逐步下线旧手写面板实现（或保留为 custom block 容器）。

## Open Questions

- union discriminator 的启发式规则是否需要扩展到 `enum`/`oneOf` 的 title 等场景,还是坚持“可证明才做 selector”？
- map 的 key 编辑（rename）是否需要在后续引入受控方案,或长期保持由 custom block 处理？
- schema 的 order/section 分组规则是否需要引入显式 metadata（例如 `schema.order`/`ui:section`）,还是保持 v1 的简单规则？

