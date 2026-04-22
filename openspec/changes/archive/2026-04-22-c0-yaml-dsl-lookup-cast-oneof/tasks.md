## 1. Schema SSOT（lookup_cast one-of）

- [x] 1.1 修改 `src/scalim/dsl/yaml_dsl/schema_dsl/constants.py` 中的 `LOOKUP_CAST_SCHEMA`：从 `{name, sep?}` 升级为 one-of 分支结构 `{auto|int|str|sep_first: {...}}`
- [x] 1.2 同步更新 `DESC_LOOKUP_CAST*` 文案/示例，使 hover 能表达新语法与 float key 约束（`auto` 拒绝 float）
- [x] 1.3 运行 `just gen-yaml-dsl-schema` 刷新生成物 `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`（禁止手改 `.gen.`）

## 2. Runtime 校验与解析（fail-fast + 迁移提示）

- [x] 2.1 修改 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/validators/sources.py` 的 `_validate_lookup_cast`：按 one-of 结构校验互斥分支，并拒绝 `sep` 出现在 `int/str/auto` 分支
- [x] 2.2 为 legacy 写法 `lookup_cast: {name: ...}` 增加显式校验错误与可照抄的迁移提示（例如 `lookup_cast: {int: {}}` / `lookup_cast: {sep_first: {sep: ","}}`）
- [x] 2.3 修改 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/parsers/sources.py` 的 `_parse_lookup_cast`：解析 one-of 结构并产出内部 `LookupCastConfig(name, sep)`（或等价结构）；legacy 形态直接报错
- [x] 2.4 回归验证 source 级与 step 级路径均生效：`sources.*.lookup_cast` 与 `relations.*.steps[*].lookup_cast` 都走同一解析/校验逻辑

## 3. Tests/fixtures 全量升级（不做兼容）

- [x] 3.1 全局替换测试/fixture 中的旧语法 `lookup_cast: {name: ...}` → 新语法分支对象（`rg -n \"lookup_cast\" tests notebooks packages` 定位）
- [x] 3.2 新增/更新用例覆盖 fail-fast：
  - legacy `{name: ...}` 必须失败且包含迁移提示
  - `lookup_cast: {int: {sep: ","}}` 必须失败（分支参数不匹配）
  - `lookup_cast` 同时声明多个分支必须失败
- [x] 3.3 确认 relation signature / cache signature / snapshots 不受影响（IR 仍为 `LookupCastSpecIr(name, sep)`）

## 4. 文档 SSOT 升级 + 生成物刷新

- [x] 4.1 更新 `docs/doc/yaml-dsl/user-guide.md` 中 `3.3.3` 与 `4.3` 的 `lookup_cast` 写法与示例（SSOT；不改 `docs/site/**`）
- [x] 4.2 运行 `just gen-docs` 刷新 `schema-reference.gen.md`、站点页面等生成物/注入块（禁止手改注入区块内部与 `.gen.`）

## 5. 验收与门禁

- [x] 5.1 运行 `just qa` 确认 lint/tests + drift gate 通过
- [x] 5.2 运行 `just openspec-check` 确认 sanitize + `openspec validate --all --strict --no-interactive` 通过
