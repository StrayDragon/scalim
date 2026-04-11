## 1. 抽出 validation service（Phase 0，保持行为不变）

- [ ] 1.1 新增“纯服务层”模块 `src/scalim/dsl/yaml_dsl/validation_service.py`：实现 `validate_demand_file(...) -> ValidationPayload` 与 `validate_workflow_file(...) -> WorkflowValidationResult`
- [ ] 1.2 service 层仅返回结构化 payload（errors/warnings/locations/附加信息），不负责 rich/文本渲染；并复用既有 `ConfigValidator`/`ErrorEnvelope`/`YamlLocationIndex` 等基础设施

## 2. CLI 薄化（args → service → renderer）

- [ ] 2.1 重构 `src/scalim/cli/yaml_dsl.py:_run_validate`：保留 args 解析与输出渲染，将业务校验 pipeline 全部下沉到 service，显著降低复杂度并尽量移除 `# noqa: C901`
- [ ] 2.2 保持对外输出结构与关键字段一致（json/text），退出码决策逻辑不变

## 3. 测试（service 单测 + CLI 输出快照）

- [ ] 3.1 为 service 增加单测：覆盖 schema 缺失、workflow 语法错误、workflow 语义错误、run demand resolve 失败、demand schema 校验失败等典型分支
- [ ] 3.2 在 `tests/test_yaml_dsl_cli_output.py`（或新增覆盖）补充 CLI json/text 输出快照，确保 Phase 0 不发生意外漂移

## 4. 规范同步与验收门禁

- [ ] 4.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/yaml-dsl-cli-validation/spec.md` 增加 “CLI validate MUST delegate to reusable service layer” 的要求
- [ ] 4.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 4.3 运行 `just quick-qa-only-py`（或 `just qa`）作为最终验收
