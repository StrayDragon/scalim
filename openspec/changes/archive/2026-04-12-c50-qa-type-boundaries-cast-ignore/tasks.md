## 1. 引入 runtime narrowing helper（方案 A）

- [ ] 1.1 新增内部模块作为类型窄化 SSOT（位置以依赖边界为准，例如 `src/scalim/_internal/type_narrowing.py` 或 YAML parsing 内部 utils），提供 `as_mapping/as_list/require_str/mapping_get_str` 等常用 helper
- [ ] 1.2 在 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/validator.py` 与 `.../parsers/outputs.py` 等解析逻辑中逐步替换散落的 `isinstance + cast` 片段，统一错误 path 与消息口径

## 2. 收敛 `type: ignore` 到边界函数并补测试矩阵（方案 B）

- [ ] 2.1 在 `src/scalim/spec/ir/_sources.py` 将动态签名调用相关 `type: ignore[call-arg]` 收敛到 1~2 个边界函数内（调用方不再出现 ignore）
- [ ] 2.2 新增测试矩阵覆盖 `_call_normalize_call_by` 的主要签名形态与 fallback（`fn(result, ctx)` / keyword-only ctx / `fn(result)` / `**kwargs` / `inspect.signature` 不可用等）

## 3. 低风险 ignore 清理（Literal 返回值）

- [ ] 3.1 在 `src/scalim/execution/key_normalization.py` 将 `type: ignore[return-value]` 替换为显式窄化写法（例如 `cast(KeyNormalizationMode, raw)`），避免无意义 ignore 扩散

## 4. 规范同步与验收门禁

- [ ] 4.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/testing-quality/spec.md` 增加 “type narrowing/ignore MUST be centralized + 动态调用以测试矩阵兜底” 的治理要求
- [ ] 4.2 运行 `just quick-qa-only-py`（含 basedpyright/ruff/cast 扫描等门禁）作为最终验收
- [ ] 4.3 运行 `just openspec-check` 校验 OpenSpec 工件

