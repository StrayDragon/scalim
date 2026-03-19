## Why

`frontend/scalim-yaml-dsl-editor` 的 Visual 编辑面板当前包含大量手写面板与（或）依赖 schema-form 类库来渲染 JSON Schema 表单。
这带来两个长期问题:

- 维护成本高: schema 演进时需要同步更新多处 UI/写回逻辑,容易产生“某些路径可视化可编辑,某些只能回到 YAML”的割裂体验。
- 依赖风险高: 现成的 Svelte schema-form 方案往往对 Svelte 主版本有更高 peer 依赖要求,升级链路会把风险扩散到整个编辑器工程。

本变更的目标是在不引入第三方 schema-form（尤其是不引入 Svelte 升级风险）的前提下,用“Schema → Editable Blocks”的内部模块把 schema 渲染与写回动作标准化,并保留按 YAML path 的手写嵌入点,承接关系链/派生依赖/输出字段等强交互复杂区。

## What Changes

- 新增内部子模块 `src/libs/schema_blocks/`:
  - 将（deref + 展开后的）JSON Schema 转为一组可渲染的 `EditableBlock[]`
  - 输出稳定的写回抽象 `BlockAction`（set/delete/ensure/insert/move 等）,统一映射到现有 YAML patch 能力（`yaml_patch.ts` + `yaml_edit_ops.ts`）,以保证注释/anchors/格式 roundtrip 稳定
  - 对 `anyOf/oneOf` 提供“可推断分支”的 selector;不可推断时统一标记为 unsupported 并回退到 raw YAML
- 新增 OverrideRegistry（按 YAML path pattern 注册）:
  - 精确匹配 > glob 匹配 > schema 默认生成
  - priority 高的覆盖低的
  - 覆盖命中后默认不再生成该节点 children（除非 custom builder 显式组合）
- UI 集成:
  - 新增 `SchemaBlocksPanel.svelte`（或等价入口）以 schema-driven 的 blocks 渲染可视化编辑面板,在运行时替换/覆盖现有大部分手写面板（Visual/Derived/Output/Relations/...）
  - 写回统一复用现有 patch decision 交互（AliasDecisionModal / PatchPreviewModal）
- 保留并嵌入强交互手写块:
  - 关系链图/Derived deps 图、输出字段候选项/别名/锚点解析等,通过 custom block + overrides 挂载到指定 YAML path（例如 `relations`、`fields`、`outputs.0.fields`）
- 明确不采用第三方 schema-form 库:
  - 例如 `@sjsf/form`（Svelte JSON Schema Form）存在但 peer 依赖要求更高的 Svelte 版本,且默认对象表单难以满足“YAML patch 保真写回”的目标

## Capabilities

### New Capabilities
- `yaml-dsl-editor-schema-blocks`: 在编辑器内提供 schema-driven 的 Editable Blocks 生成、渲染与按 YAML path 的手写嵌入机制,并将所有写回收敛到既有 YAML patch/decision UX。

### Modified Capabilities
<!-- (none) -->

## Impact

- 影响范围限定在 `frontend/scalim-yaml-dsl-editor/**`:
  - 新增 `src/libs/schema_blocks/**` 与对应单测（node:test 风格）
  - 新增/替换面板渲染入口（Visual 面板或新面板 + 路由/选择入口）
  - 逐步拆分现有面板的强交互组件,以 custom blocks 的形式复用
- 依赖层面:
  - v1 不引入第三方 schema-form 库;避免 Svelte 主版本升级链路风险
- 用户体验与兼容性:
  - 继续以 YAML 文本为 SSOT,所有结构化编辑写回走 patch,最大化保留注释/anchors/格式
  - 复杂 union 场景提供明确的 fallback（raw YAML + 跳转定位）,而不是 silent failure

