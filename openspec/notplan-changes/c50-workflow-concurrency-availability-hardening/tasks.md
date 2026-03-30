## 1. Workflow options SSOT（DSL + schema）

- [ ] 1.1 扩展 workflow config 类型以表达 `resources_wait` 与 `write_locks`（SSOT：`src/scalim/dsl/by_yaml/workflow_config/_models.py`）
- [ ] 1.2 在 `src/scalim/dsl/by_yaml/workflow_config/_parse.py` 解析与校验新 options（有限非负数/enum/unknown keys fail-fast）
- [ ] 1.3 扩展 workflow schema SSOT（`src/scalim/dsl/by_yaml/schema_dsl/builder.py`）并刷新生成物（`just gen-yaml-dsl-schema`；验收：`just schema-drift-check`）

## 2. IR 传播（DSL → IR → runtime）

- [ ] 2.1 扩展 `WorkflowOptionsIr`（SSOT：`src/scalim/spec/ir/_workflow.py`）并在 `src/scalim/dsl/by_yaml/workflow_compile.py` 完成映射
- [ ] 2.2 将 IR options 注入 workflow runtime（`src/scalim/workflow/execute.py` → `WorkflowResourceManager(...)` 等）

## 3. 资源 join/wait 默认超时（避免 hang）

- [ ] 3.1 将 workflow 共享资源 join/wait 默认策略改为有限超时（默认 `max_wait_s=600`；不得允许 `None` 表达无限等待）
- [ ] 3.2 超时错误必须包含 resource_id/type/wait_kind/wait_s/max_wait_s/owner 信息；补齐回归测试（避免 `sleep` 抖动,用 monotonic + 明确完成信号）

## 4. 写锁后端（file/mkdir/none）与治理

- [ ] 4.1 在 `src/scalim/workflow/resources_base.py` 实现可选后端（`file`/`mkdir`/`none`）,并标准化锁路径/owner 信息写入与释放
- [ ] 4.2 将 backend 策略在 workbook/csv/sheetbook/books export 写入路径统一应用（不得各自漂移）
- [ ] 4.3 新增回归：`mkdir` 后端并发冲突/清理、`backend=none` 不产生锁产物（确保 xdist 并发下稳定）

## 5. 文档 + 生成物 + gates

- [ ] 5.1 更新 `docs/doc/yaml-dsl/workflow.md`：新增 `resources_wait`/`write_locks` 说明、Dagster/容器避免 hang 指南、NFS/共享盘风险提示；如涉及 injected blocks 刷新 `just gen-docs`（验收：`just docs-drift-check`）
- [ ] 5.2 运行规范与质量门禁：`just openspec-check`（OpenSpec sanitize+validate）、`just qa`

## 6. Server/Web API 场景（后续决策）

- [ ] 6.1 明确是否需要提供“输出路径随机后缀/隔离”的 opt-in 能力（若需要,优先以 entrypoint override 方式落地,并考虑拆分为独立 change）
