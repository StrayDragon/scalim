## 1. schema_blocks Scaffolding

- [ ] 1.1 新增 `frontend/scalim-yaml-dsl-editor/src/libs/schema_blocks/` 目录与导出入口
- [ ] 1.2 定义 `EditableBlock` 数据模型与 `BlockAction` 写回抽象（包含 actions 集合）
- [ ] 1.3 实现 schema 基础遍历与展开工具（`$ref`/`allOf`/description/title/examples 读取）

## 2. Block Builder（Schema → Blocks）

- [ ] 2.1 实现 `buildBlocks(...)`：scalar/enum/object 的生成与排序规则（required 置顶 + 其余稳定排序）
- [ ] 2.2 实现 `buildBlocks(...)`：array（增删/移动 items）与 map（additionalProperties/patternProperties）生成
- [ ] 2.3 实现 union 推断（anyOf/oneOf）：可判定分支生成 selector；不可判定标记 unsupported + raw YAML fallback 元数据

## 3. OverrideRegistry（手写嵌入机制）

- [ ] 3.1 实现 OverrideRegistry（精确 path / glob / priority）与固定优先级规则（精确>glob>默认）
- [ ] 3.2 支持 override 命中后默认不生成 children；并提供 custom builder 组合 `buildBlocks` 的能力
- [ ] 3.3 为强交互区域定义首批 overrides（例如 `relations`、`fields`、`outputs.*.fields` 等路径）

## 4. Writeback Integration（Blocks → YAML Patch）

- [ ] 4.1 实现 `BlockAction` → `YamlEditOp` 的映射层（set/delete/ensure/insert/remove/move）
- [ ] 4.2 将 actions 全部接入 `applyYamlEditOp` 并复用 safe/rewrite/decision 的现有链路
- [ ] 4.3 补齐 raw YAML 跳转能力（从 block/yamlPath 定位到 YAML 文本位置）

## 5. UI 集成（SchemaBlocksPanel）

- [ ] 5.1 新增 `SchemaBlocksPanel.svelte`：左侧 outline + 右侧 sections 渲染 blocks
- [ ] 5.2 面板支持“缺失/可创建”状态（写回仍走 patch）,并与现有面板选择入口集成（可保留回退）
- [ ] 5.3 支持 custom blocks（Svelte component）在 schema-driven 面板内渲染并触发写回 actions

## 6. Tests / QA / Governance

- [ ] 6.1 新增单测：`buildBlocks` 对 object/array/map/enum/scalar/required/description 的生成稳定性
- [ ] 6.2 新增单测：OverrideRegistry 多匹配优先级（priority + 精确>glob）与“覆盖后不生成 children”规则
- [ ] 6.3 新增单测：union 推断成功生成 selector；不可推断时回退 unsupported + raw YAML
- [ ] 6.4 新增单测：写回动作映射到 `applyYamlEditOp` 后的 patch plan 预期（safe vs rewrite）
- [ ] 6.5 手工验收：用 `public/examples/*.yaml` 完成创建缺失 section、编辑 enum、编辑数组 items、触发 alias decision、跳转 raw YAML
- [ ] 6.6 质量门禁：运行 `just qa` 与 `just openspec-check`；确认本变更不手改任何 `.gen.` 文件或 `BEGIN/END AUTOGEN` 注入区块（若未来需要,以 SSOT + 生成入口为准）

