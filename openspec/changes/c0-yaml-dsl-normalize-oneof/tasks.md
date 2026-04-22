## 1. Schema SSOT（normalize one-of）

- [ ] 1.1 修改 `src/scalim/dsl/yaml_dsl/schema_dsl/constants.py` 中的 `NORMALIZE_SCHEMA`：从 `{kind, ...}` 升级为分支 one-of 结构 `{index_by_key|take_first|project_fields|map_values: {...}, call_by?: <ref>}`
- [ ] 1.2 修改 `src/scalim/dsl/yaml_dsl/schema_dsl/constants.py` 中的 `_NORMALIZE_STEP_SCHEMA`：从 `{kind, ...}` 升级为 step 分支 one-of 结构 `{take_first: {...}} | {project_fields: {...}}`
- [ ] 1.3 同步更新 `DESC_SOURCE_NORMALIZE*` 文案/示例（将 `normalize.kind=...` 示例升级为分支写法；保持语义与默认值不变）
- [ ] 1.4 运行 `just gen-yaml-dsl-schema` 刷新生成物 `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`（禁止手改 `.gen.`）

## 2. Runtime 校验与解析（fail-fast + 迁移提示）

- [ ] 2.1 修改 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/validators/sources.py` 的 `_validate_normalize`：按分支 one-of 结构校验互斥分支与分支字段合法性（含 `map_values.steps[*]` step 分支）
- [ ] 2.2 为 legacy 写法增加显式迁移提示：
  - `normalize: {kind: index_by_key, ...}` → `normalize: {index_by_key: {...}}`
  - `steps: [{kind: take_first, ...}]` → `steps: [{take_first: {...}}]`
- [ ] 2.3 修改 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/parsers/sources.py` 的 `_parse_normalize`：解析新分支结构并产出内部 `NormalizeConfig`（或等价结构），同时确保 `normalize.call_by` 路径保持为 `sources.*.normalize.call_by`
- [ ] 2.4 回归验证 `normalize` 的四种分支与默认值：`index_by_key/take_first/project_fields/map_values`（含 steps pipeline）在 IR 转换与执行期行为保持一致

## 3. Tests/fixtures 全量升级（不做兼容）

- [ ] 3.1 全局替换测试/fixture 中的旧语法 `normalize.kind: ...` / `steps[*].kind: ...` → 新语法（建议 `rg -n \"normalize\\.kind|steps\\[\\*\\]\\.kind|kind: (index_by_key|take_first|project_fields|map_values)\" tests notebooks packages docs` 定位）
- [ ] 3.2 新增/更新用例覆盖 fail-fast：
  - legacy `{kind: ...}` 必须失败且包含迁移提示
  - normalize 同时声明多个分支必须失败
  - `on_none` 出现在非 `index_by_key` 分支必须失败
  - `map_values.steps[*]` step 同时声明多个分支必须失败

## 4. 文档/Skill SSOT 升级 + 生成物刷新

- [ ] 4.1 更新 `docs/doc/yaml-dsl/user-guide.md` 中 `normalize` 章节的写法与示例（SSOT；不改 `docs/site/**`）
- [ ] 4.2 更新 `agentdev/skills/scalim-yaml-dsl/**` 中涉及 `normalize.kind` 的示例与升级文档（SSOT；不改 generated 引用清单）
- [ ] 4.3 运行 `just gen-docs` 刷新 `schema-reference.gen.md`、站点页面等生成物/注入块（禁止手改注入区块内部与 `.gen.`）

## 5. 验收与门禁

- [ ] 5.1 运行 `just qa` 确认 lint/tests + drift gate 通过
- [ ] 5.2 运行 `just openspec-check` 确认 sanitize + `openspec validate --all --strict --no-interactive` 通过
