## 1. Project Config + Schema (Python 3.6 boundary)

- [ ] 1.1 扩展 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/project_config.py`：新增 `yaml_dsl.lsp.hover` 解析与 fail-fast 校验（未知字段名/类型直接报错）
- [ ] 1.2 扩展 schema SSOT `src/scalim/dsl/yaml_dsl/schema_dsl/models/scalim_yaml.py`：为 `yaml_dsl.lsp.hover.*` 增加 JSON Schema 定义（enum + array 顺序保留）
- [ ] 1.3 刷新生成物 `src/scalim/dsl/yaml_dsl/schema/scalim_yaml.gen.json`（生成入口：`just gen-yaml-dsl-schema`；禁止手工编辑）
- [ ] 1.4 运行 drift/gate：`just schema-drift-check` + `just py36-compat-check`（确保 SSOT→生成物一致，且不破坏 Python 3.6 兼容）

## 2. LSP Hover Rendering (Markdown + Config)

- [ ] 2.1 在 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py` 中切换 hover 输出为 `MarkupKind.Markdown`（仅对本 server 返回的 hover）
- [ ] 2.2 引入 `scalim.yaml` hover 配置加载与缓存（建议以 `scalim_yaml_path + mtime` 为 key；在 hover/diagnostics 侧按需 reload；不依赖重启 server）
- [ ] 2.3 在 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py` 中实现通用 Markdown card helper（标题/章节/列表/表格 + escaping）
- [ ] 2.4 实现配置驱动渲染框架：为每个 hover 类型定义 allowlist + renderer 映射，并按 `yaml_dsl.lsp.hover.*` 字段列表输出

## 3. Hover 类型增强（按能力验收）

- [ ] 3.1 `entity_reference` hover：source/relation/output/workflow_run 卡片化（优先复用 `YamlDslEntityDeclaration.summary/detail/yaml_path`）
- [ ] 3.2 `field_reference` hover（relation steps 的 `source.field_id`）：在可用时复用 `effective_view` 做 source_id 消歧与定义位置展示；不可用时降级到 entity_index
- [ ] 3.3 `python_reference` hover：在 docstring 之外补齐可静态获得的字段（type/module/defined_at/parameters），并支持按配置裁剪
- [ ] 3.4 `builtin_callable` hover：关联 Python 定义信息（复用 python_reference 渲染），并支持表格化参数展示（如可获得）
- [ ] 3.5 `aggregate_field` hover：对 out_field_id 与 global field_id 做区分展示（来源、output_index、group_by 等），并保证稳定输出
- [ ] 3.6 `callby_parameter` hover（kwargs value field token）：复用 output field hover 信息，并在 aggregate call_by 场景保持与 aggregate_field 一致的降级策略

## 4. Examples / QA

- [ ] 4.1 更新/新增 VSCode fixture：`extras/vscode-scalim/fixtures/scalim.yaml` 增加 `yaml_dsl.lsp.hover` 示例（用于文档与手动回归）
- [ ] 4.2 为关键 hover renderer 增加最小回归测试（若现有 packages 无测试基建，则在项目既有 pytest 结构内新增覆盖点）
- [ ] 4.3 运行质量门禁：`just type-check-packages-yaml-dsl-lsp` + `just check-only-py`（必要时再跑 `just qa`）
