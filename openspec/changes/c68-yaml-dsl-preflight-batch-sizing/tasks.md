## 1. Policy signal：hooks/events 扩展点

- [ ] 1.1 定义 `pre_use_batch_size` 的 signal/event 常量与 payload 契约（decision 对象需支持 override + history）
- [ ] 1.2 在 hooks 分发层支持该 signal：
  - 建议走 typed dispatch（新增 `HOOK_TYPED_DISPATCH_MAP` 条目 → `on_pre_use_batch_size`），避免影响所有 `on_event` hook
  - 不要求改动 `IExecutionHook`（保持非破坏性；handler 作为可选方法）
- [ ] 1.3 明确 policy signal 的异常语义（默认 fail-fast；需要 warn-and-skip 时由 hook 自行吞异常并发出 warning）

## 2. Standalone demand：pre-run_ir 阶段注入

- [ ] 2.1 在 `run()` 路径中加入 policy signal 阶段点：位于 `_compile(...)` 之后、`run_ir(...)` 之前
- [ ] 2.2 保证 `compile(...)` 入口保持纯编译：不得触发任何 policy signal（避免把外部 I/O 带入编译/校验链路）
- [ ] 2.3 precedence：显式 `RunOptions(batch_size=<int|None>)` 时跳过 signal；并确保 `None` 语义穿透 execution(no-chunking)
- [ ] 2.4 pre-run_ir debug：输出/事件中可见最终 batch_size 与 decision.history（便于回溯是谁改的、为什么）

## 3. Workflow：per-run 注入与上下文

- [ ] 3.1 在每个 node 的 runtime compile 之后、进入该 node 的 `run_ir` 之前发射 `pre_use_batch_size`（使用 per-run effective options 口径）
- [ ] 3.2 precedence：workflow per-run patch 显式提供 `batch_size=<int|None>` 时跳过 signal
- [ ] 3.3 为 policy hook 提供必要上下文（run_id、demand_path、init_vars 已渲染等），以便按 demand profile 自适应

## 4. 参考实现与最佳实践（文档/样例）

- [ ] 4.1 提供一个推荐 hook 模板（示例：执行一次 total_rows COUNT/estimate → max_batches/clamp 推导 → override）
- [ ] 4.2（可选）定义一个 loader 协议/约定（例如 loader 函数携带 `__scalim_preflight_total_rows__` callable），用于减少调用侧注册成本

## 5. 测试与门禁

- [ ] 5.1 单测：显式 batch_size 跳过 signal；signal 改写生效；`None` 显式禁用分批仍可穿透
- [ ] 5.2 workflow 单测：per-run patch 与 signal precedence；不同 run 的上下文隔离
- [ ] 5.3 跑通门禁：`just qa` 与 `just openspec-check`

