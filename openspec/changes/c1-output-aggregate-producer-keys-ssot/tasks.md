## 1. SSOT 枚举模块

- [ ] 1.1 新增 `src/scalim/dsl/by_yaml/schema_dsl/output_enums.py`（Python 3.6 兼容）并定义 `AGG_METRIC_PRODUCER_KEYS/AGG_RANK_PRODUCER_KEYS/AGG_POST_PRODUCER_KEYS`
- [ ] 1.2 为 SSOT 常量补齐最小文档字符串与导出列表（避免被误当作内部变量）

## 2. 迁移重复常量

- [ ] 2.1 `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` 删除本地 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS/_POST_FUNC_KEYS` 等重复枚举，改为从 SSOT 导入
- [ ] 2.2 `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py` 删除本地 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS`，改为从 SSOT 导入
- [ ] 2.3 `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py` 将硬编码 post producer keys（例如 `("score_by_rank", "call_by", "compute")`）改为基于 SSOT（禁止手写字符串集合）
- [ ] 2.4 `src/scalim/dsl/by_yaml/runtime/introspection.py` 删除本地 `_AGG_FUNC_KEYS/_RANK_FUNC_KEYS`，并将默认 `post_ids` 逻辑改为基于 SSOT（方案 A：默认包含 `compute`，与 runtime 默认输出列对齐）

## 3. Schema / Editor 对齐（结构校验零漂移）

- [ ] 3.1 `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py` 将 aggregate producer keys 的 schema 组装（anyOf/required）改为基于 SSOT，并增加“schema 覆盖全集”的强校验（缺 key/多 key fail-fast）
- [ ] 3.2 运行 `just gen-yaml-dsl-editor-schema` 生成并提交：
  - `src/scalim/dsl/by_yaml/schema/demand.gen.json`
  - `frontend/scalim-yaml-dsl-editor/public/schema/demand.gen.json`
  - `frontend/scalim-yaml-dsl-editor/src/schema/demand.gen.json`

## 4. 防漂移护栏（回归测试）

- [ ] 4.1 新增单元测试（行为回归）：覆盖 aggregate + `compute` + 未显式 `outputs.*.fields` 的场景，确保 `load_output_config()` 默认 `output_fields` 与 runtime 输出列一致
- [ ] 4.2 新增单元测试（防漂移）：断言 parser/runtime/introspection 引用同一份 SSOT 常量对象（更强），至少断言集合一致（更弱）
- [ ] 4.3 若发现当前各层行为存在“有意差异”，在测试中写清差异的理由并固定（避免再次漂移）

## 5. 验收

- [ ] 5.1 运行 `just qa`（或最小子集）确保无 lint/test 回归
- [ ] 5.2 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
