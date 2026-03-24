## Context

- workflow runtime 已模块化拆分,但核心编排与资源实现仍存在巨型函数,维护成本高。
- 当前入口层通过写模块全局变量实现依赖注入（便于测试 monkeypatch）,但并发/并行测试下存在串扰风险。
- 多处并发/诊断类测试依赖真实时间阈值（例如 0.01s）与 `time.sleep`,在慢 CI 环境易抖动；另有子进程调用无 timeout 可能导致 suite 卡死。

## Goals / Non-Goals

**Goals:**
- 将关键模块的复杂度拆分为可读、可测的阶段化单元,减少 `# noqa C901/...` 的集中出现。
- 用显式依赖注入替代模块全局写入,保证并发运行可预期。
- JSON-like 校验规则收敛为 SSOT,避免多处实现漂移。
- 提升测试稳定性：减少时间抖动,避免短超时误报,避免卡死。

**Non-Goals:**
- 不改变对外 YAML authoring surface 与默认语义（除非显式标注为 BREAKING 并更新 specs）。
- 不把本 change 扩展为新的 workflow 能力（仅聚焦质量/稳定性护栏）。

## Decisions

1) 阶段化拆分策略
- 优先拆分“准备/执行/提交/报告”等阶段,把 I/O 与纯逻辑分离,保持每个阶段可单测。
- 保持稳定导入路径（entrypoints 仍是稳定入口）,避免大规模重命名/搬迁造成外部漂移。

2) 依赖注入方式
- 将 workflow 执行器函数（例如 `run_ir`）作为参数/RunOptions 传递,并为测试提供显式替换入口,避免写模块属性。

3) JSON-like 校验 SSOT
- 抽取统一 helper（Python 3.6 compatible）,由 workflow ctx、cache signature 等路径共享。
- 校验失败的错误信息与路径字段保持稳定,便于诊断与测试断言。

4) 测试稳定性策略
- 并发/死锁检测类测试以 `Event/Barrier` 作为同步信号,避免依赖真实时间窗口。
- 对 `join(timeout=...)` 等 timeout 采用更稳健的上限（复用统一常量）,避免慢 CI 误报。
- 为 `subprocess.check_output` 添加 timeout 并在超时时输出诊断信息。

## Risks / Trade-offs

- [重构回归] 拆分过程可能引入细微行为差异 → 以小步提交、保持测试覆盖与对比用例缓解。
- [测试变更] 放宽 timeout 可能掩盖真实死锁 → 通过更明确的完成信号与日志/状态断言保证“没死锁”而不是“1s 内跑完”。 

