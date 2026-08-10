# Proposal: trusted-mode-defense-in-depth

> 一句话描述: 在 resolver trusted mode（`trusted_allow_all_modules`）下保留 `DANGEROUS_MODULES` denylist 作为最后一层防线，并补充运行时审计日志与风险文档。

## Why

当 `resolver_trusted_mode=trusted_allow_all_modules` + `SCALIM_ALLOW_TRUSTED_ALL_MODULES=1` 时，`SecurePythonReferenceResolver` 的 `DANGEROUS_MODULES` denylist 被完全绕过（因为 `allowed_modules=frozenset(['*'])` 使 `ResolverPolicy.check()` 全部通过）。这意味着 YAML 可解析并调用 `os.system`、`subprocess.check_output` 等任意危险模块，等同于 RCE。

虽然已有 3 层 gate（mode 枚举 + env var + 配置验证），但：
- env var 设置后**进程全局**生效
- 无运行时审计日志（仅初始化时 warning）
- denylist 是最后一道防线，不应被完全解除

## What Changes

1. **在 trusted mode 下保留 `DANGEROUS_MODULES` denylist**（defense-in-depth）：即使 `allowed_modules=*`，仍拒绝 `os`、`subprocess`、`pickle` 等模块
2. **添加运行时审计日志**：每次 `resolve()` 调用在 trusted mode 下记录目标模块/函数（`security_logger.info` 级别）
3. **文档化**：在 resolver 公共 API docstring 和安全文档中明确标注 trusted mode 的风险边界

## Capabilities

### Modified Capabilities

- `yaml-dsl-allowlist-policy` — 增加 trusted mode defense-in-depth 要求

## Impact

- **代码区域**: `src/scalim/dsl/yaml_dsl/runtime/references.py` (`SecurePythonReferenceResolver`, `PythonReferenceResolver`)
- **破坏性**: 低 — 仅影响显式启用 trusted mode 的用户，且是收紧行为
- **安全**: Critical → 降为 High（保留最后一层防护）
