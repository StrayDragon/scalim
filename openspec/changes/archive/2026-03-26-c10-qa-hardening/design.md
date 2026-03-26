## Context

本变更覆盖三类问题：
- **安全**：trusted-mode 放宽过强且缺乏门控；unsafe 入口需要显式可观测的风险告警与审计；计算审计与错误信息可能泄露敏感表达式/字段值。
- **竞态**：缓存池逐出与加载窗口存在 TOCTOU；部分执行器/缓存结构在并发下存在无锁访问点。
- **维护性**：少数热点函数复杂度偏高（C901）、异常捕获过宽、fixture 状态未恢复、文件操作存在 TOCTOU 模式。

## Goals / Non-Goals

**Goals:**
- 修复关键竞态，保证并发下不出现重复加载/缓存孤儿/线程间状态损坏
- 收紧安全边界：让“放宽为代码执行能力”的路径必须显式且可审计
- 降低测试 flake：统一 timeout 策略，减少硬编码的 wall-clock 依赖
- 维护性改进不改变业务语义（以等价拆分/收敛为主）

**Non-Goals:**
- 不在本变更引入新的 DSL 能力或新的公开运行入口
- 不在本变更实现大规模架构重写（仅针对热点与风险点做外科式修复）

## Decisions

- **trusted allow-all 门控**：`trusted_allow_all_modules` 仅在环境变量 `SCALIM_ALLOW_TRUSTED_ALL_MODULES=1` 时允许启用，并持续输出高风险告警。
- **unsafe 入口审计**：`unsafe_run/unsafe_compile` 调用必须产生 warning 级审计日志，并对 legacy sandbox 输出弃用警告。
- **缓存/执行器并发控制**：在存在共享实例/多线程访问风险的路径上加锁（`ThreadLoopExecutor` submit/shutdown；`SecureComputeEngine` LRU；缓存容器的 per-key 写路径）。
- **PII 保护**：默认审计与异常日志避免输出表达式原文/字段值；提供可选的脱敏审计回调。
- **TOCTOU 改造**：以 EAFP 替换 `exists()+unlink()` 等模式，避免并发/外部干预下的窗口问题。

## Risks / Trade-offs

- 更严格的 fail-fast（trusted-mode env gate）可能会影响内部测试/脚本；但这是期望行为，且提供了明确的开启方式。
- 更强的审计/告警可能增加日志量；但仅发生在显式 `unsafe` 路径或明确开启的模式下。
- C901 拆分属于结构性重构，需依赖 `just qa` 覆盖回归以降低语义漂移风险。
