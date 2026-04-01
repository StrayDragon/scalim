## 1. YAML Schema & Config Parsing (SSOT)

- [x] 1.1 扩展 workflow YAML schema: 新增 `workflow.options.output_staging`（SSOT: `src/scalim/dsl/by_yaml/schema_dsl/**`）
- [x] 1.2 运行 `just gen-yaml-dsl-schema` 刷新 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（生成物禁止手改）
- [x] 1.3 更新 workflow YAML 解析/类型: 解析 `output_staging` 并做 fail-fast 校验（保持 Python 3.6 兼容）

## 2. IR Boundary

- [x] 2.1 扩展 `WorkflowOptionsIr`: 携带 `output_staging` 进入 runtime（SSOT: `src/scalim/spec/ir/_workflow.py`）
- [x] 2.2 确认 YAML → IR → runtime 的传递链路可测（回归测试覆盖）

## 3. Runtime: Output Staging + Publish

- [x] 3.1 共享输出 commit 阶段写入 staging 唯一路径
- [x] 3.2 workflow 成功结束后覆盖发布到最终路径（原子 replace）
- [x] 3.3 清理策略: success 清理 / failure 可配置保留
- [x] 3.4 移除 workflow runtime 对共享输出的 write lock file 依赖

## 4. Tests / Docs / Gates

- [x] 4.1 新增回归测试：staging publish/cleanup 与 keep_on_success/keep_on_failure 行为
- [x] 4.2 更新 docs：`docs/doc/yaml-dsl/workflow.md` 补充 output_staging 用法与默认语义
- [x] 4.3 运行 `just openspec-check` 确保 OpenSpec 工件一致性
- [x] 4.4 运行 `just qa` 通过 lint/tests + drift checks
