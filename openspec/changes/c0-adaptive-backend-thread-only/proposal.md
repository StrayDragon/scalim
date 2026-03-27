## Why

当前 `parallel_mode=adaptive` 的实现同时维护 thread/process/async 多套 backend,带来:
- 维护面与测试面显著扩大(分支多、覆盖要求高),且对 CI 稳定性与排障成本不友好。
- process/async backend 相关语义与 guardrails 复杂,在 Python 3.6 运行时边界下更难长期稳定演进。

本变更选择“接口保留、实现移除”的裁剪路径:保留扩展 seam 与调度结构,将主线实现收敛为 thread-only,为未来回加实现保留清晰落点。

## What Changes

- 保留 adaptive 的整体架构与扩展点（policy/overrides/scheduler 分发结构）,但主线仅内置 thread backend。
- **BREAKING** 删除 process/async backend 的实现代码与测试;当 policy/用户配置选择到非 thread backend 时,立即抛出明确错误,作为未来回加实现的占位。
- 收敛 adaptive pool 的创建逻辑为 `ThreadPoolExecutor`(保留 `PipelineOverrides.adaptive_executor_cls` 注入点)。
- 文档与规范同步更新为“backend seam 仍在,当前仅支持 thread”。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `parallel-execution`: adaptive backend seam 保留但仅支持 thread;选择 process/async 时稳定抛错并给出恢复实现的指引。
- `explicit-extension-points`: overrides 仍提供显式 seam,但不再承诺可注入 process/async backend executor;仅 thread 路径为内置支持。

## Impact

- 代码: `src/scalim/execution/adaptive/`、`src/scalim/execution/pipeline/base/_adaptive_pool.py`、`src/scalim/execution/pipeline/overrides.py` 等。
- 测试: 删除/改写所有依赖 process/async backend 的用例,回归 thread-only 行为。
- 文档: `docs/doc/architecture/parallel-modes.md` 作为 SSOT 手写文档直接修改;不编辑任何 `.gen.` 文件或 `BEGIN/END AUTOGEN` 注入区块(如需刷新生成物,入口为 `just gen-docs`)。

