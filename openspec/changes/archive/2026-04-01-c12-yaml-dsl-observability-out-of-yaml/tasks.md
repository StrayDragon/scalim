## 1. YAML 侧迁出与迁移提示

- [x] 1.1 从 demand / workflow 的 schema、parser 与校验路径中移除 `observability.*` 主线支持,并为已知 legacy keys 增加“warning + ignore + migration hint”过渡逻辑; schema SSOT 为 `src/scalim/dsl/by_yaml/schema_dsl/**`,生成物用 `just gen-yaml-dsl-schema` 或 `just gen` 刷新
- [x] 1.2 为 legacy observability warning 与普通 unknown-field 错误分别补测试,确保只对已知迁移项降级为 warning

## 2. Runtime 承载面

- [x] 2.1 明确 Python / CLI runtime entrypoints 中 observability 的 typed surface 与推荐用法,覆盖 `components`、`viz_config` 与自定义 hook / observer 集成
- [x] 2.2 补 runtime 侧示例与最小回归用例,确保不依赖 YAML `observability.*` 也能完成常见观测集成

## 3. 材料与验收

- [x] 3.1 同步更新 `docs/doc/**`、skills、notebooks、fixtures 与示例材料,移除对 YAML `observability.*` 的主线推荐; 若有注入区块使用 `just gen-docs` 刷新并以 `just qa` 验收
- [x] 3.2 运行 `just openspec-check`、`just qa` 与 `openspec status --change c12-yaml-dsl-observability-out-of-yaml` 确认工件和漂移门禁通过
