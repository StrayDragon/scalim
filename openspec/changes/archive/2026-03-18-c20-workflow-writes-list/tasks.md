## 1. Authoring Surface & Schema（BREAKING）

- [x] 1.1 更新 workflow 解析器：在 `src/scalim/dsl/by_yaml/workflow.py` 移除 `run.write_to`，新增 `run.writes`(list) 并复用现有五类 intent 的字段校验逻辑；旧字段 `write_to` 出现时 MUST fail-fast 并给出可复制的迁移提示。
- [x] 1.2 更新 workflow JSON Schema 的 SSOT：在 `src/scalim/dsl/by_yaml/schema_dsl/` 中为 `writes` 建模（items 为 oneOf 五类 intent），并通过 `scripts/gen-yaml-dsl-schema.py` 生成 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（禁止手改生成物）。
- [x] 1.3 更新 SSOT 文档 `docs/doc/yaml-dsl/workflow.md`：将 `write_to` 章节升级为 `writes`，补齐“一个 run 多 outputs → 多条 writes”示例；运行 `just gen-docs` 刷新 `docs/doc/yaml-dsl/schema-reference.gen.md` 与 `docs/doc/yaml-dsl/upgrades/*.gen.md`（禁止手改 `.gen.md`）。

## 2. IR 编译与执行链路

- [x] 2.1 在 `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py` 将 `runs[*].writes` 编译为多个 write nodes（每条 intent 一个节点），并保持 per-resource 链式 deps 的确定性写入顺序（run 顺序 + writes 顺序）。
- [x] 2.2 升级 sheetbook 读屏障：当 producer run 存在多个 sheetbook 写入节点时，将这些节点全部追加为其 direct dependents 的 deps（保守但正确）。
- [x] 2.3 增强错误信息：当 write intent 引用未知 resource_id / output_id 时，错误 MUST 包含 `run_id`、intent kind、resource_id、output_id 与配置路径。

## 3. 测试与回归

- [x] 3.1 新增 workflow 解析单测：`writes` 允许多个 intents；单个 intent 必须恰好一个 key；出现 `write_to` 时明确报错并给迁移建议。
- [x] 3.2 新增集成测试：一个 run 产出 `metrics/detail` 两个 CSV outputs，并通过两条 `writes` 写入同一个 sheetbook/workbook 的不同 sheet；验证导出/commit 结果包含两张 sheet 且数据一致。
- [x] 3.3 新增确定性测试：`max_concurrency>1` 下多次运行同一 workflow，写入顺序与结果 MUST 与声明顺序一致（对同一资源互斥串行）。

## 4. 规范同步与门禁

- [x] 4.1 更新增量规范：`openspec/changes/c20-workflow-writes-list/specs/*/spec.md` 覆盖 `write_to` → `writes` 的 REQUIREMENTS 与 Scenarios。
- [x] 4.2 运行 `just openspec-check`（sanitize + `openspec validate --all --strict --no-interactive`）确保工件结构与脱敏规则通过。
- [x] 4.3 运行 `just qa` 或最小覆盖 workflow 相关测试，确保无回归。
