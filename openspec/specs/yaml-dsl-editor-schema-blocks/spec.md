# yaml-dsl-editor-schema-blocks Specification

## Purpose
TBD - created by archiving change c1-yaml-dsl-editor-schema-blocks. Update Purpose after archive.
## Requirements
### Requirement: schema_blocks 生成稳定的 Editable Blocks
系统 MUST 在 `frontend/scalim-yaml-dsl-editor/src/libs/schema_blocks/` 提供 `buildBlocks(...) -> EditableBlock[]`,用于把（deref + 展开后的）JSON Schema 节点转换为可渲染的块结构。

每个 `EditableBlock` MUST 至少包含:

- `id`（稳定,默认由 `yamlPath.join(".")` 派生）
- `yamlPath`（数组索引用 `"0"` 等字符串）
- `kind`（scalar/enum/object/array/map/union/custom/unsupported）
- `title/description`（优先使用 `schema.title/markdownDescription/description`）
- `required`（基于父级 required 计算；未知时为 null）
- `schemaNode`（包含展开后的 schema 片段,并保留原始 node 以便 debug）
- `actions`（标准化写回动作集合）
- `children`（当 kind 为 object/array/map 等容器类型时）

#### Scenario: object properties 生成 blocks 且 id 稳定
- **WHEN** 给定一个包含 `properties` 与 `required` 的 object schema 并调用 `buildBlocks`
- **THEN** 系统 MUST 为每个 property 生成一个 `EditableBlock`
- **AND** 每个 block 的 `id` MUST 与其 `yamlPath.join(\".\")` 一致
- **AND** required 字段 MUST 标记为 `required: true`

### Requirement: schema_blocks 支持 $ref 与 allOf/基础结构展开
系统 MUST 支持解析并展开以下 JSON Schema 特性用于 block 生成:

- `$ref`（本地 ref）
- `allOf`
- `properties` / `required` / `default`
- `enum` / `const`
- `items`
- `additionalProperties` / `patternProperties`（用于 map block）
- `description` / `markdownDescription` / `title` / `examples`

#### Scenario: $ref 可被解析并用于 block 生成
- **WHEN** schema node 使用 `$ref` 指向本地定义并调用 `buildBlocks`
- **THEN** 系统 MUST 对该 `$ref` 进行 deref 并按解引用后的 schema 生成 blocks

### Requirement: OverrideRegistry 按 YAML path 注册并遵循固定优先级规则
系统 MUST 提供 OverrideRegistry（或等价机制）用于按 YAML path 注册 overrides。

匹配与覆盖规则 MUST 固定为:

1. 精确 path 匹配 > glob 匹配 > schema 默认生成
2. `priority` 高的 override 覆盖低的
3. override 命中后,该节点的默认 children MUST NOT 继续生成（除非 custom builder 显式组合 `buildBlocks`）

#### Scenario: 同一路径多匹配时精确匹配优先
- **WHEN** 同一 yamlPath 同时命中一个精确匹配与一个 glob 匹配 override
- **THEN** 系统 MUST 选择精确匹配 override
- **AND** 不应再继续生成该节点的默认 children

### Requirement: anyOf/oneOf 仅在可推断分支时生成 union selector,否则 fallback
系统 MUST 在 schema 节点包含 `anyOf` 或 `oneOf` 时,按以下规则生成 blocks 与 UI fallback:

- **IF** 分支存在明确 discriminator（例如 const 字段,或唯一 required key 集合）
  - 系统 MUST 生成 `kind: \"union\"` 的 block,并提供可选择分支的 selector
- **ELSE**
  - 系统 MUST 将该节点标记为 `kind: \"unsupported\"`（或等价标记）
  - 并在 UI 中提供清晰提示与“跳转到 raw YAML 编辑”的入口

#### Scenario: 不可推断 union 时标记 unsupported 并提供 raw YAML 回退入口
- **WHEN** `anyOf/oneOf` 的各分支无法通过 discriminator 规则推断当前分支
- **THEN** 系统 MUST 将该节点标记为 unsupported
- **AND** UI MUST 提供跳转到对应 YAML 文本位置的入口以进行 raw 编辑

### Requirement: BlockAction 写回必须统一映射到 YAML patch/decision UX
系统 MUST 为 blocks 提供标准化写回动作（BlockAction）,并将其统一映射为 `YamlEditOp`,最终通过 `applyYamlEditOp` 应用到 `yamlText`。

- **IF** patch plan 为 safe
  - 系统 MUST 直接更新 `yamlText`
- **IF** patch plan 需要 rewrite 或带 decision
  - 系统 MUST 复用现有 PatchPreview/AliasDecision 交互链路,在用户确认后再更新 `yamlText`

#### Scenario: rewrite 计划必须先经 patch preview/decision
- **WHEN** 某个 block action 触发的 patch plan 需要 rewrite 或 decision
- **THEN** 系统 MUST 展示与现有链路一致的预览/决策交互
- **AND** 用户取消时 MUST 保持原 `yamlText` 不变

### Requirement: SchemaBlocksPanel 以 blocks 渲染 schema-driven 面板并提供 outline
系统 MUST 提供一个 schema-driven 的编辑面板（例如 `SchemaBlocksPanel.svelte`）,并以 `EditableBlock[]` 作为渲染输入:

- 面板 MUST 提供从顶层 properties 生成的 outline,并支持点击导航到对应 YAML 文本位置
- 面板 MUST 按固定规则分组渲染 blocks（例如: 顶层 properties 为一级分组,object 内 properties 为二级）
- 当 YAML 中缺失某个可创建的 section 时,面板 MUST 显示“缺失/可创建”状态并提供创建入口（写回仍走 patch）

#### Scenario: 缺失 section 可被创建且写回走 patch
- **WHEN** YAML 中缺失某个顶层 properties key
- **THEN** 面板 MUST 显示缺失状态并提供创建入口
- **AND** 创建动作 MUST 通过 patch 写回到 YAML 文本

### Requirement: 强交互区域必须可通过 custom blocks 嵌入
系统 MUST 支持 overrides 提供 `kind: \"custom\"` 的 blocks,并通过 Svelte 组件承接强交互编辑区（例如关系链图、派生依赖图、输出字段候选/别名/锚点解析）。

#### Scenario: relations 区域可用 custom block 替换默认生成
- **WHEN** overrides 对 `relations`（或等价 YAML path）注册 custom block
- **THEN** schema-driven 面板 MUST 渲染该 custom block 组件,而不是默认 schema blocks

