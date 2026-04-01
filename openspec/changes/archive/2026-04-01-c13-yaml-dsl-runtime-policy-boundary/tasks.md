## 1. Demand runtime policy 迁出

- [x] 1.1 从 demand schema / parser / validate 中迁出 `guardrails.*`、`retry.*`、`batch_size` 与 demand `failure_policy`,并为旧写法补 migration hint; schema SSOT 为 `src/scalim/dsl/by_yaml/schema_dsl/**`,生成物用 `just gen-yaml-dsl-schema` 或 `just gen` 刷新
- [x] 1.2 在 Python / CLI runtime entrypoints 中补齐这些字段的 typed surface 与回归测试,确保不依赖 YAML 也能表达相同 runtime policy

## 2. Workflow runtime policy 分层

- [x] 2.1 从 workflow YAML 迁出 `workflow.options.resources_wait.*` 与 `workflow.output_staging.*`,并为运行入口补对应 typed surface / 参数映射
- [x] 2.2 保留 workflow `failure_policy` 作为稳定 orchestration knob,补语义测试以确保其与 demand `failure_policy` 的边界清晰

## 3. 文档与验收

- [x] 3.1 更新 `docs/doc/yaml-dsl/**`、CLI 帮助文档与相关 skill 指引,说明哪些策略已迁出到 runtime entrypoints; 文档 SSOT 为 `docs/doc/**`,若涉及注入区块使用 `just gen-docs` 刷新并以 `just qa` 验收
- [x] 3.2 运行 `just openspec-check`、`just qa` 与 `openspec status --change c13-yaml-dsl-runtime-policy-boundary` 确认工件与质量门禁通过
