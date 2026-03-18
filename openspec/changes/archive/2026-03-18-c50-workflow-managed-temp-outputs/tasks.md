## 1. Schema/模型（Authoring Surface）

- [x] 1.1 更新输出容器模型：在 `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py` 允许 `type: csv` 的 `container.path` 省略/为空，并在 `markdownDescription` 明确“仅 workflow 托管 writes 场景可用”的边界与警告。
- [x] 1.2 运行生成入口刷新生成物（禁止手改生成物）：
  - `scripts/gen-yaml-dsl-schema.py` → `src/scalim/dsl/by_yaml/schema/demand.gen.json`
  - `just gen-docs` → schema reference / upgrades 等 `.gen.md`

## 2. 编译/运行期注入与校验

- [x] 2.1 扩展 `compile_output_composition_from_yaml(...)`（`src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`）：在启用 workflow 托管参数时，为 pathless CSV outputs 生成实际路径；未启用时保持 fail-fast。
- [x] 2.2 在 `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py` 的 compile-on-ready 阶段：
  - 计算当前 run 被 write intents 引用的 output_ids；
  - 创建 run-scoped managed temp dir；
  - 将 managed 输出路径注入 demand 编译；
  - 将生成的路径发布到 artifacts_dir（outputs mapping），供 write nodes 消费。
- [x] 2.3 漏配校验：pathless CSV output 若未被任何 write intent 引用，workflow MUST fail-fast 并指出 `run_id`/`output_id`/配置路径。

## 3. 清理语义

- [x] 3.1 在 workflow commit/discard/finally 中统一清理 managed temp dir，确保成功与失败分支都不会泄漏临时文件。
- [ ] 3.2 （可选）提供可信排障开关以保留临时目录（默认关闭）。

## 4. 测试与回归

- [x] 4.1 单测：standalone demand 编译遇到 pathless CSV output 必须 fail-fast 并给出“仅 workflow 托管可用”的提示。
- [x] 4.2 集成测试：workflow 中 pathless CSV output 被 writes 消费并写入共享资源；workflow 结束后临时目录被清理。

## 5. 规范与门禁

- [x] 5.1 新增/更新增量规范：`openspec/changes/c50-workflow-managed-temp-outputs/specs/**/spec.md` 覆盖托管临时输出的 REQUIREMENTS 与场景。
- [x] 5.2 运行 `just openspec-check` 确保 OpenSpec 工件结构与脱敏规则通过。
- [x] 5.3 运行 `just qa`（至少覆盖 workflow/output 相关测试）确保无回归。
