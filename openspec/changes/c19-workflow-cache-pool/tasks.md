## 1. CachePool 契约与数据结构

- [ ] 1.1 定义 CachePool 的最小接口（acquire/release/evict + 可选 get_or_load）
- [ ] 1.2 定义 entry 的 signature 结构（JSON-safe、可复现、含 rendered_params）
- [ ] 1.3 定义冲突策略：`error` / `separate` / `warn`（含错误摘要结构）

## 2. Signature 计算与渲染边界

- [ ] 2.1 实现“渲染后的 params”规范化（确保 dict/list 顺序与数值表示可复现）
- [ ] 2.2 适配 `{$init_var: ...}` / `{$ctx: ...}`：确保 signature 在 compile-on-ready 渲染后计算

## 3. 生命周期：DAG-based refcount + pin

- [ ] 3.1 基于 Workflow IR 推导 consumer set（refcount 上界）
- [ ] 3.2 运行时在 node acquire/release 时维护 refcount，并在 refcount=0 时释放/可淘汰
- [ ] 3.3 实现 pin 机制（强制常驻到 workflow 结束）

## 4. 预算与淘汰策略

- [ ] 4.1 支持预算配置（SSOT: max_entries）
- [ ] 4.2 定义超限策略：fail-fast 或仅淘汰 refcount=0 的 entries（例如 LRU）

## 5. 观测集成（与 workflow-observability-bridge 对齐）

- [ ] 5.1 发出 cache acquire/release/evict 事件点（复用 `workflow_exec_id` / `workflow_node_id`）
- [ ] 5.2 错误与告警可诊断：冲突策略为 warn/separate 时提供可观测告警与差异摘要

## 6. 迁移与验收

- [ ] 6.1 升级 workflow YAML：`share_preload_cache` → `cache_pool`（仓内一次性升级，不保留旧字段兼容）
- [ ] 6.2 更新 workflow schema SSOT（`src/scalim/dsl/by_yaml/schema_dsl/**`）并运行 `just gen-yaml-dsl-schema`（禁止手改 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`）
- [ ] 6.3 如涉及 docs/注入块,更新 SSOT 并运行 `just gen-docs`（禁止手改 `.gen.` 与 injected blocks）
- [ ] 6.4 集成测试：复用正确性、冲突策略行为、refcount 释放正确性、预算策略
- [ ] 6.5 运行 `just qa`
- [ ] 6.6 运行 `just openspec-check`
