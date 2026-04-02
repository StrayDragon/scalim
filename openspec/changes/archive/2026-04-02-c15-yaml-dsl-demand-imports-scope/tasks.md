## 1. Imports allow-matrix 收敛

- [x] 1.1 明确并实现 demand `imports` / `$import` 的 allow-matrix,仅覆盖 `main_source`、`sources.*`、`fields.*`、`relations.*` 与仍属于资源声明的 `resources.*`
- [x] 1.2 在 parser / validator / schema / effective-YAML 渲染链路中统一执行该 allow-matrix,并对越界路径提供稳定诊断; schema SSOT 为 `src/scalim/dsl/by_yaml/schema_dsl/**`,相关展开逻辑 SSOT 为 `src/scalim/dsl/by_yaml/_internal/config_parsing/**`,如需生成 schema 用 `just gen-yaml-dsl-schema` 或 `just gen`

## 2. Workflow 与非 authoring 区域封口

- [x] 2.1 显式禁止 workflow imports expansion,确保 workflow schema、validate 与文档口径一致
- [x] 2.2 禁止 imports 进入 runtime-policy / output-extras 区域,并为典型误用场景补回归测试

## 3. 文档与验收

- [x] 3.1 更新 `docs/doc/yaml-dsl/**`、skills 与示例,用具体例子说明哪些 `resources.*` 片段适合跨文件复用,以及哪些路径不再允许 `$import`; 若涉及 injected blocks 使用 `just gen-docs` 刷新并以 `just qa` 验收
- [x] 3.2 运行 `just openspec-check`、`just qa` 与 `openspec status --change c15-yaml-dsl-demand-imports-scope` 确认工件与门禁通过
