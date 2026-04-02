## 1. 资源分层与写策略收敛

- [x] 1.1 明确并实现 `resources.books/files` 作为基础资源声明、workflow / `RunOverrides.resources` 作为 overlay / deep-merge 的统一契约,补冲突与 precedence 回归测试
- [x] 1.2 以 `resources.books.*.write_defaults` 为 workbook 写策略 SSOT,收缩 `outputs[*].write` 到最小 output-local 行为,并同步 schema / parser / compiler 约束; schema SSOT 为 `src/scalim/dsl/by_yaml/schema_dsl/**`,生成物用 `just gen-yaml-dsl-schema` 或 `just gen` 刷新

## 2. Output extras 迁出

- [x] 2.1 设计并实现 runtime typed output extras,承接 `meta` / `audit` 的 workbook 附加能力
- [x] 2.2 从 YAML 主线迁出 `meta` / `audit`,补 migration hint 与相关回归测试,确保 workbook 依赖与失败模式有清晰诊断

## 3. 文档、typed overrides 与验收

- [x] 3.1 更新 `docs/doc/yaml-dsl/**`、runtime override API 文档与示例,用四层输出模型重写职责边界; 文档 SSOT 为 `docs/doc/**`,若涉及 injected blocks 使用 `just gen-docs` 刷新并以 `just qa` 验收
- [x] 3.2 运行 `just openspec-check`、`just qa` 与 `openspec status --change c14-yaml-dsl-write-policy-and-output-extras` 确认工件、schema 生成物与测试门禁通过
