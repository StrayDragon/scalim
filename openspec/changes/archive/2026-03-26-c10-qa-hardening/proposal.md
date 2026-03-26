## Why

基于六维审查（安全、代码质量、漏洞、竞态条件、测试稳定性、可维护性），当前实现存在若干 **安全边界与并发正确性** 的薄弱点，同时部分测试与热点函数复杂度偏高，导致 CI/并发场景下更易出现 flake 与排障成本上升。

本变更的目标是：
- 在不引入新功能语义的前提下，修复关键竞态与安全 footgun
- 提升测试稳定性与可维护性（降低复杂度、收窄异常、减少 TOCTOU）
- 为后续演进提供可自证的验证入口（`just gen` / `just qa` + 压力/重复测试）

## What Changes

- **并发正确性**：修复 `WorkflowCachePool` 逐出与加载竞态；补齐 `PreloadCache`/`ThreadLoopExecutor` 的并发路径护栏/锁。
- **安全边界**：为 `trusted_allow_all_modules` 增加环境变量门控；`unsafe_*` 入口补充审计日志与弃用警告；`builtin_callables` 解析复用主 allowlist 约束。
- **隐私与可诊断性**：为计算审计提供脱敏回调；错误日志与异常信息用表达式哈希替代原文，降低 PII 泄漏风险。
- **测试稳定性**：统一测试超时常量，替换硬编码超时，减少 xdist/慢机 flake。
- **维护性/质量**：拆分 C901 热点函数；收窄宽泛异常；将多处 TOCTOU 文件操作改为 EAFP；修复 module-scoped fixture 的状态恢复。

## Capabilities

### Modified Capabilities
- `workflow-cache-pool`: eviction/refcount 路径与 in-flight load 协同正确性
- `yaml-dsl-allowlist-policy`: `trusted_allow_all_modules` 的显式环境门控
- `yaml-dsl-builtin-callables`: builtin vocab 的解析不得绕过 allowlist 约束
- `yaml-template-vars-sandbox`: `unsafe` 入口必须提供明确风险告警/审计与 legacy 弃用提示
- `field-compute`: 审计与错误信息避免泄露原始表达式/字段值；编译缓存并发安全

## Impact

- 受影响代码集中在 `src/scalim/` 的 execution/runtime/security/sinks/workflow，以及 `tests/` 的并发与稳定性用例。
- 该变更以“修复/重构”为主，不引入新的公共 API 面向用户的行为扩展；但会带来更严格的 fail-fast（trusted-mode env gate）与更强的审计/告警输出（unsafe 入口）。
