## Context

本变更聚焦两类风险收敛：

1) **依赖漏洞（依赖扫描）**：通过 `uv export` 从 `uv.lock` 导出 pinned 依赖后，使用 `pip-audit -s osv --no-deps --disable-pip` 扫描发现：
- `marimo 0.22.0` → `CVE-2026-39987`
- `pytest 9.0.2` → `CVE-2025-71176`
- `uv 0.11.3` → `GHSA-pjjw-68hj-v9mw`（本机 `uv` 已较新，但 `uv.lock` 仍锁在旧版本）

2) **并行执行（adaptive）安全/稳定性风险**：当前实现整体数据竞争控制较好（overlay commit 在主线程按 plan 顺序执行），但存在一些可被外部输入放大的边界问题：
- 显式 `max_workers` 无上限（潜在 DoS 风险）。
- `run_tasks_in_pool` 无任务级超时/中断路径；一旦 loader/用户代码卡死，异常路径下线程池关闭等待可能导致“已报错但仍长时间 hang”。
- 任务提交循环存在跨 pool 的 head-of-line blocking，影响吞吐与公平性。
- 并行模式事件回放为分桶顺序（typed hooks 先、observer/on_event 后），与顺序模式逐事件 interleaving 语义不完全一致，streaming sink 可能出现“数据先写出、事件后出现”的观感差异。
- HookCaptureManager 订阅发现基于 `source.hooks` 的快照；运行期间动态 register/unregister hooks 与当前锁粒度（engine 仅对单次 run 加锁）存在语义缝隙，需要明确约束或加固。

约束：
- 运行时必须兼容 Python 3.6；dev/tooling 可为 3.10+。
- 文档治理：禁止手改任何 `*.gen.*` 或 injected blocks；若涉及注入/生成，统一走 `just gen-docs`，质量门禁走 `just qa`。

## Goals / Non-Goals

**Goals:**

- 以**最小扰动**方式更新 `uv.lock` 中受影响依赖（优先 `uv lock -P ...`），消除已知 CVE/GHSA。
- 为显式 `max_workers` 增加 guardrail（cap 或至少 warning），并在 YAML/IR 入口处补充/强化校验，避免外部输入放大并发导致资源耗尽。
- 为 adaptive 执行路径补齐“卡死/长时间不返回”的可控退路（至少避免异常路径无限等待），并提供可观测的诊断信息（哪些任务卡住、等待了多久）。
- 修复提交循环 head-of-line blocking，提升跨 pool 吞吐；补回归测试覆盖。
- 文档明确并行模式的事件回放顺序语义与线程安全使用约束（cache/hook 注册）。

**Non-Goals:**

- 不做大范围 requirements 变更；仅新增一份轻量 guardrails spec 用于文档化并约束关键安全边界。
- 不引入新的并行后端（process/async）或复杂的任务强制终止机制（Python 线程无法安全强杀）。
- 不承诺“绝对保序”的 observability replay（若需要，另开变更讨论 typed/observer 事件合并为单序列的兼容性影响）。

## Decisions

1. **依赖升级策略：锁文件最小更新**
   - 首选执行：`uv lock -P pytest -P marimo -P uv`。
   - 约束：不将 dev-only 依赖升级扩散到运行时依赖边界；必要时仅调整 `pyproject.toml` 中对应组/extra 的上限/下限，以确保 resolver 合法。

2. **`max_workers` guardrail：在“解析 + 运行时”两处兜底**
   - 运行时兜底：在 `resolve_adaptive_max_workers` 统一做上限裁剪与诊断（warning 或显式标记被 cap）。
   - 入口兜底：在 YAML/IR 入口（`workflow_entrypoints` / `contracts`）对明显异常的并发输入做校验/告警，强调“外部输入不可直接放大并发”。
   - 上限策略：倾向使用一个保守且与 CPU 相关的 cap（例如 `min(user, min(256, max(32, cpu*5)))`），并在文档/日志中明确该 cap 的存在与目的（DoS guardrail）。

3. **任务级超时/中断：提供“可诊断的 fail-fast”，并承认线程不可强杀**
   - 在 `run_tasks_in_pool` 等待 futures 的路径上引入可选 `timeout_seconds`，用于在长时间无进展时抛出明确异常（包含未完成任务 keys 与建议排查点）。
   - 当触发超时或异常时：取消可取消的 futures，并在可行范围内让 pipeline 尽快返回（避免“报错后仍 hang 很久”）。
   - 文档明确限制：线程池中的运行中任务无法被强制终止；如需硬隔离/硬超时，建议在上层用子进程隔离执行。

4. **提交循环 HOL blocking：调整 token 获取顺序**
   - 将 pool token 获取放在 global token 之前（避免 pool 饱和时占用 global token），并补一条回归测试：两 pool 场景下，小池限流不应阻塞其它 pool 的提交。

5. **可观测性 replay 顺序：保持现状 + 文档明确**
   - 本变更仅澄清并行模式的 replay 顺序与顺序模式的差异（typed hooks 与 observer/on_event 分桶回放）。
   - 若未来需要绝对保序（特别是 streaming sink），另开变更评估把两类事件合并为单序列回放的兼容性与性能影响。

6. **线程安全使用约束：以文档 + 轻量运行期校验为主**
   - `preloaded_cache`：文档声明并发运行时不得共享普通 `dict`；必要时增加运行期 warning（检测到 `dict` 且并行度>1）。
   - hooks 动态注册：明确“不支持在 run 期间跨线程 register/unregister hooks”；必要时将捕获逻辑视为运行开始时快照语义。

## Risks / Trade-offs

- **行为差异风险（`max_workers` 被 cap）** → Mitigation：默认仅对极端值生效；日志/warning 明确提示；入口文档强调该 guardrail。
- **“超时后仍有后台线程运行”的资源风险** → Mitigation：超时只作为 fail-fast 诊断手段；默认关闭；文档建议对不受信任/可能卡死的 loader 用子进程隔离。
- **调度改动引入公平性/吞吐回归** → Mitigation：补回归测试覆盖两 pool 场景；必要时在调度器加统计输出用于定位。

## Migration Plan

- 实施顺序：
  1) 更新 `uv.lock` 并跑依赖/测试门禁。
  2) 增加 `max_workers` guardrail（运行时 + 入口校验）并补文档说明。
  3) 调整提交循环 token 顺序并加回归测试。
  4) 引入可选 timeout（默认关闭），补诊断错误信息与文档。
  5) 更新并行模式文档（顺序语义、cache/hook 使用约束）。
- 验收与漂移门禁：
  - `just qa`（lint/tests/drift checks）
  - `just openspec-check`（sanitize + validate）

## Open Questions

- `max_workers` 的默认 cap 是否需要可配置（env var / runtime option）？若可配置，如何避免成为新的外部放大入口？
> runtime option 放在合适的位置即可 你可以通过 just gen-public-api-jump-imports 来获得所有可公开用户的api 我希望类似 preset 那样 当用户创建了 seq 和 adaptive 两种不同预设的数据结构时可以选择的options 不同 合理来处理这个选项放置点

- 超时异常应该归类为哪种公开错误类型（是否需要一个稳定的异常类供下游捕获）？
> 需要

- 是否需要在事件流中补充一个“replay boundary”/“flush complete”类事件，帮助 streaming sink 更明确地处理分桶回放语义？
> 需要
