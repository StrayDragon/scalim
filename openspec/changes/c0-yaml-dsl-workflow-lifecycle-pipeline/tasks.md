## 1. Lifecycle Pipeline（SSOT + Harness）

- [ ] 1.1 引入 workflow lifecycle pipeline 的阶段结果对象（parse/preload/effective-merge/preflight/execute），并用单一 orchestrator 串起来（避免入口漂移）
- [ ] 1.2 提供测试用 harness：允许在单测中“执行到某个阶段并取回阶段产物”（例如到 preflight，但不启动 engine）
- [ ] 1.3 **DONE 验收**：新增单测覆盖“执行到 preflight 时 engine 未启动 + 能拿到 per-run effective options 的阶段产物”

## 2. Demand Parser-only Boundary（路线 B）

- [ ] 2.1 拆分/重构 demand loader：提供 parser-only API（只做解析与结构抽取），并禁止暴露 runtime-only diagnostics knobs（例如 `validate_unique_field_names` 这种开关）
- [ ] 2.2 将 workflow structural preload 迁移为仅调用 parser-only 路径（不得抢跑 runtime-only diagnostics；不得通过“传 False”这种方式绕过）
- [ ] 2.3 **DONE 验收**：新增单测证明 structural preload 对 duplicate effective field display names 不失败（无论 `validate_unique_field_names` 默认值如何）

## 3. 解析口径一致性（避免 parse drift）

- [ ] 3.1 统一 demand YAML 的解析设置来源：structural preload / preflight / runtime compile MUST 复用同一套“解析上下文”（至少包含 `template_vars`、`rendered_yaml_max_len`、`allowed_yaml_roots`）
- [ ] 3.2 **DONE 验收**：新增回归单测（设置很小的 `rendered_yaml_max_len` + 模板渲染 demand YAML）证明超限会在 structural preload 阶段 fail-fast（不得拖到 preflight/runtime compile 才失败）

## 4. SSOT：Effective Outputs/Resources Trigger Semantics

- [ ] 4.1 抽取 effective outputs/resources 的 SSOT helper（包含关键触发判定：例如是否会写 `header_fields_output_by=name` 的 header）
- [ ] 4.2 改造 workflow preflight 与 runtime compile/diagnostics runner 复用同一 SSOT helper（避免 drift）
- [ ] 4.3 **DONE 验收**：补齐“示例 A/示例 B”单测（runtime overrides 能关闭/开启触发条件，且 preflight 行为符合 effective 口径）

## 5. Preflight 重构（IO-free + deterministic + fail-fast）

- [ ] 5.1 重构 preflight：checks 消费 structural preload 的结果（例如 `DemandConfig`），preflight 阶段不得再次读取/解析 demand YAML
- [ ] 5.2 保持确定性：runs 按 decl_order，checks 按 registry 顺序；第一个错误直接 raise（不聚合）
- [ ] 5.3 **DONE 验收**：新增单测证明 preflight 不做 demand YAML IO（例如 demand_path 不存在也不会触发读取），并且 fail-fast 抛出第一个 run 的错误

## 6. EntryPoint Refactor（保持外部语义不变）

- [ ] 6.1 重构 `run_workflow(...)`：以 pipeline 为 SSOT 编排 parse/preload/effective-merge/preflight/execute（保持公开 API 不变）
- [ ] 6.2 **DONE 验收**：新增集成单测证明 preflight 失败会在 engine 启动前中止（例如注入 `run_ir_fn` 记录调用，断言未被调用）
- [ ] 6.3 **DONE 验收**：现有 workflow 回归用例全部通过（重点：`failure_policy` 不影响 preflight 失败语义）

## 7. Tests & Boundary Guards（长期可维护）

- [ ] 7.1 更新现有 preflight 单测以适配“preflight 不再读 demand YAML”的新结构（保持覆盖与可读性）
- [ ] 7.2 增加“边界回归”测试：确保 structural preload 代码路径不会导入/调用 runtime-only diagnostics runner（轻量 import/调用约束）

## 8. Docs / Generated Boundaries & Validation Gates（验收口径）

- [ ] 8.1 **SSOT（手工维护）**：`src/scalim/dsl/by_yaml/**`、`tests/**`、`openspec/changes/c22-yaml-dsl-workflow-lifecycle-pipeline/**`
- [ ] 8.2 **生成物/注入区块**：若变更触达任何 `*.gen.*` 或 `BEGIN/END AUTOGEN:*` 区块，必须修改对应 SSOT 并运行 `just gen-docs`（禁止手改生成物）
- [ ] 8.3 OpenSpec 验收：`just openspec-check`
- [ ] 8.4 质量门禁验收：`just qa`

## 9. Integrated Acceptance（Definition of Done）

- [ ] 9.1 所有新增/修改的单测覆盖以下维度：pipeline 阶段、parser-only 边界、effective 口径、preflight IO-free、fail-fast、preflight-before-engine
- [ ] 9.2 `just qa` 通过
- [ ] 9.3 `just openspec-check` 通过

