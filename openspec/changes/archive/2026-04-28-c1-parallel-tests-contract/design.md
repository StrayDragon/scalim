## Context

- `just qa` 当前运行 `pytest tests/ -q -n auto --cov=...`，因此“并行执行”是事实上的质量门禁路径。
- 现存问题集中在测试侧对 `scalim_misc` 的模块全局状态修改:
  - `tests/conftest.py` 修改 `scalim_misc.example_report_ir.data_loader.random_delay`
  - 多处测试通过 `scalim_misc.demo_big_data_report.loaders.set_config/get_config` 修改全局 config

这些做法在 xdist 的“多进程并行”下大概率不会互相影响,但它们:
- 隐含并发假设,难以审核
- 容易在未来引入线程并行/复用解释器的执行器时变为 flaky 来源
- 违背“依赖注入、无模块全局 mutation”的测试工程准则

## Goals / Non-Goals

Goals:
- 明确并落地“非 bench 测试在 `pytest -n auto` 下必须稳定通过”的仓库契约。
- 让涉及全局状态的 patch 变得显式、可复用、可加锁(线程并行下不出错)。

Non-Goals:
- 不在本 change 中重写所有 demo/样例代码为纯函数式依赖注入(若需要,后续可单开 change)。

## Decisions

1. 契约层面: 以 xdist 为基线,同时不把测试实现绑死在“只有进程并行”
- 规范明确要求 `pytest-xdist -n auto` 必须通过。
- 测试实现上,对确实需要修改全局状态的路径加全局锁,避免未来线程并行执行器引入问题。

2. 对 example_report_ir 使用“替换对象”而非“原地修改属性”
- 方案: 构造 `PandasDataLoader(random_delay=0.0)` 并 monkeypatch `example_report_ir.data_loader`。
- 优点: patch 点集中(一个变量),恢复由 pytest monkeypatch 机制管理,不需要手工 finally。

3. 对 demo_big_data_report config 使用“集中化工具 + 锁”
- 方案: 提供一个测试辅助上下文(或 fixture),负责:
  - 读取 prev config
  - 在持锁区间内 set_config(new)
  - yield 测试
  - finally 恢复 prev
- 优点: 所有调用点复用同一个实现,避免每处自己写 try/finally。

## Risks / Trade-offs

- [风险] 通过锁序列化全局 config patch 会降低并行度。
  - 缓解: 受影响的测试数量有限；后续可通过“把 config 注入到 runtime_bindings/builders”消除锁。

- [风险] monkeypatch 替换 loader 可能略增每 worker 初始化成本。
  - 缓解: 将 fixture scope 调整为 `session` 或 `worker` 级(在 xdist 下每个 worker 一次)；并确保 PandasDataLoader 初始化可接受。

## Migration Plan

- 先改测试与 fixtures,保证 `just qa` 无回归。
- 若外部用户依赖 `scalim_misc` 的全局 set_config 语义,该变更保持现状(仍可用)；本 change 的重点是测试侧隔离,不强制更改包 API。

## Open Questions

- 是否需要在 CI 增加一条“更激进的并行 smoke”(例如 `--dist loadscope`/重复跑两次)以更早暴露污染问题?
> 我觉得可以