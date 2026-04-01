## 1. Workflow schema/runtime 对齐

- [x] 1.1 收紧 `workflow.resources` 的 schema / parser / validate 契约,移除 runtime 不支持的 keys 与 `$import` 暴露,并为已知旧写法补 migration hint; schema SSOT 为 `src/scalim/dsl/by_yaml/schema_dsl/**`,生成物为 `src/scalim/dsl/by_yaml/schema/*.gen.json`,用 `just gen-yaml-dsl-schema` 或 `just gen` 刷新
- [x] 1.2 为 workflow validate / schema validate 增加回归测试,覆盖“schema 曾允许但 runtime 不支持”的高风险 case,并确保错误路径与提示文案稳定

## 2. Numeric typing 护栏

- [x] 2.1 在 schema generation 流程内加入 numeric constraints typing fail-fast,仅拦截“明确无效”的 `minimum/maximum/...` + 缺失数值类型组合
- [x] 2.2 增加仓库级 drift gate / 测试,覆盖 `workflow.resources` allowed keys 与 numeric typing 两类基础可信度问题,并纳入 `just qa`

## 3. 文档与验收

- [x] 3.1 同步 `docs/doc/yaml-dsl/**` 中关于 workflow 校验与 schema 行为的说明; 文档 SSOT 为 `docs/doc/**`,若涉及注入区块使用 `just gen-docs` 刷新并以 `just qa` 验收
- [x] 3.2 运行 `just openspec-check` 与 `openspec status --change c10-yaml-dsl-schema-workflow-alignment` 确认工件完整
