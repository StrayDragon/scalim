## Why

依赖扫描发现多项已公开漏洞（marimo / pytest / uv），且当前并行执行（adaptive）路径存在若干可被外部输入放大的资源风险（无限制 `max_workers`）与“卡死后长时间 hang”的稳定性风险（缺少任务级超时/中断）。

本变更目标是在**最小扰动**前提下完成依赖修复与执行层 guardrails，加固默认安全边界，并把并行模式下的可观测性顺序语义写清楚，降低误用与排障成本。

## What Changes

- 依赖漏洞修复（锁文件级别，最小扰动）
  - 更新 `uv.lock` 中 marimo / pytest / uv 的 pinned 版本，消除已知 CVE/GHSA（按 Python 3.10+ 能支持的最新安全版本选择；不影响运行时 Python 3.6 边界）。
  - 建议的更新方式：`uv lock -P pytest -P marimo -P uv`（仅提升相关包及其必要传递依赖）。
- 并行执行安全/稳定性 guardrails（adaptive 执行路径）
  - 对显式 `max_workers` 增加 guardrail（硬 cap 或至少 warning），避免线程池膨胀导致 CPU/内存耗尽（DoS 风险），并在 YAML/IR 入口强调“外部输入不可直接放大并发”。
  - 为 `run_tasks_in_pool` 增加任务级超时/中断策略（或至少在错误路径避免无限等待），防止 loader/用户代码卡死后“已报错但仍长时间 hang”。
  - 优化提交循环的调度方式，避免跨 pool 的 head-of-line blocking（提升多 pool 吞吐）；补充回归测试覆盖该场景。
- 并行模式使用约束与语义澄清
  - 明确 `preloaded_cache` 的线程安全要求：普通 `dict` 不应在多线程/多 engine 间共享；推荐 `PreloadCache` 或每次 `run` 使用独立 cache。
  - 在文档中明确并行模式下事件回放顺序（typed hooks vs observer/on_event 的分桶回放），特别是对 streaming sink 的影响；若不追求绝对保序则写清楚限制。
  - 澄清/加固 hook 注册的运行期假设（HookCaptureManager 发现订阅基于快照；运行期间动态 register/unregister 属于不受支持用法或需明确约束）。

## Capabilities

### New Capabilities

- `execution-adaptive-guardrails`: adaptive 并行执行的安全/稳定性护栏（显式 `max_workers` guardrail、可选 timeout 的 fail-fast 诊断语义）

### Modified Capabilities

（无）不做额外的 spec 级 REQUIREMENTS 变更；其余行为变化以“兼容性说明 + 文档”形式呈现，并避免破坏性默认行为。

## Impact

- 依赖/工具链：`uv.lock`（以及可能的 `pyproject.toml` / extras 定义中对应的版本约束）。
- 执行层：`src/scalim/execution/adaptive/**`、`src/scalim/execution/pipeline/base/**`、`src/scalim/execution/contracts.py`。
- YAML/入口校验：`src/scalim/dsl/yaml_dsl/workflow_entrypoints.py`。
- 文档：`docs/doc/architecture/parallel-modes.md`（手写 SSOT，避免编辑任何 `*.gen.*` 或 injected block；如涉及 injected block 需走 `just gen-docs`）。
