## 1. Runtime conversions

- [x] 1.1 在 `src/scalim/dsl/by_yaml/runtime/_internal/conversion_lookup.py` 新增 `cast_decimal()` 并注册 `value_cast: decimal`（`None` 透传；空白字符串→`None`；float 使用 `Decimal(str(x))`）。
- [x] 1.2 新增/调整单测覆盖 `value_cast: decimal` 的成功与失败分支（非法字符串/非法 float 字面量/不支持类型）。

## 2. Secure compute

- [x] 2.1 在 `src/scalim/dsl/by_yaml/config_parsing/security.py` 的 safe functions 白名单中加入 `Decimal`，支持 `Decimal("0.1")` 写法。
- [x] 2.2 新增单测覆盖 `compute` 使用 `Decimal(...)` 的校验与执行路径。

## 3. Schema & docs

- [x] 3.1 更新 schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/constants.py`、`src/scalim/dsl/by_yaml/schema_dsl/models/field.py`，为 `value_cast` 增加 `decimal` 枚举与 hover 文案/示例。
- [x] 3.2 生成 schema 产物（生成物禁止手改）：运行 `scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema` 刷新 `src/scalim/dsl/by_yaml/schema/demand.gen.json` 与前端编辑器 schema 镜像文件。
- [x] 3.3 更新 docs SSOT：`docs/doc/yaml-dsl/user-guide.md`，补充/替换示例为 `value_cast: decimal`。
- [x] 3.4 生成 docs 产物（`.gen.`/injected blocks 禁止手改）：运行 `just gen-docs` 刷新 `docs/doc/**/*.gen.md` 与注入区块。

## 4. Observability robustness

- [x] 4.1 在 `src/scalim/ob/presets/relations.py` 的 relations report 输出中使用 `json.dumps(..., default=str)`，避免 `Decimal`/`datetime` 等导致输出崩溃。
- [x] 4.2 新增回归测试覆盖 relations report 的 JSON 输出稳健性。

## 5. Gates

- [x] 5.1 运行 `just lint` / `just test` 确保无回归。
- [x] 5.2 运行 `just openspec-check` 确保 OpenSpec 工件结构与脱敏规则通过。

