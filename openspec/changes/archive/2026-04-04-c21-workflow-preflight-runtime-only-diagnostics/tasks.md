## 1. Preflight 框架

- [x] 1.1 新增 `workflow_preflight` 小框架（context + check interface + registry）
- [x] 1.2 在 `run_workflow(...)` 中插入 preflight 调用（engine 启动前）

## 2. v1 check: validate_unique_field_names

- [x] 2.1 基于 effective policy/overrides 口径实现 duplicate effective field display names preflight 校验
- [x] 2.2 preflight 错误信息包含 run id 与 demand 路径，fail-fast 抛第一个

## 3. Tests & QA

- [x] 3.1 新增/调整 workflow 测试：duplicate-name 变为 preflight compile error（与 `failure_policy` 无关）
- [x] 3.2 新增 workflow 测试：per-run patch 禁用 `validate_unique_field_names` 时不触发 preflight
- [x] 3.3 新增 workflow 测试：override 输出 header 政策使 preflight 不触发（effective outputs 口径）
- [x] 3.4 运行 `just qa`（或最小化 pytest 子集）确保变更无回归

## 4. Docs / Generated

- [x] 4.1 本变更不涉及 `*.gen.*` 或 injected-block 生成物；仅需确保 OpenSpec 工件通过 `just openspec-check`
