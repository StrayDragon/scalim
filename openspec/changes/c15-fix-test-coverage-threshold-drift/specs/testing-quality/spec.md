# testing-quality (delta) Specification

## MODIFIED Requirements

### Requirement: 覆盖率保持与 `--cov-fail-under` SSOT

核心模块在启用覆盖率统计的质量门禁中 MUST 达到 `openspec/specs/testing-quality/spec.md` 与 `justfile` 中 `test-gate` **共同声明的同一** `--cov-fail-under` 阈值；两处声明的整数值 MUST 完全一致，不得出现规范与实现漂移（例如规范写 100 而门禁为 99，或相反）。

若维护者调整该阈值，MUST 同时更新主规范文档与 `justfile:test-gate`，并在规范中简要记录 rationale（例如 vendor 兼容层、平台分支、合理不可覆盖行与 `pragma: no cover` 策略）。

可选：仓库 MAY 提供治理测试，从 `justfile` 解析 `test-gate` 的 `--cov-fail-under` 并与规范中的声明比对，漂移时 MUST 失败。

#### Scenario: 规范与 `test-gate` 数值一致

- **WHEN** 审阅者比对 `testing-quality` 规范中的覆盖率失败阈值与 `just test-gate` 的 pytest 参数
- **THEN** `--cov-fail-under` 的整数值 MUST 相同

#### Scenario: 低于阈值时门禁失败

- **WHEN** 通过质量门禁入口运行带覆盖率统计的非 bench 测试
- **THEN** 若核心模块覆盖率低于上述共同声明阈值，执行 MUST 失败

#### Scenario: 漂移治理测试（若存在）

- **WHEN** 运行覆盖率阈值 SSOT 漂移治理测试
- **THEN** 若规范与 `justfile` 声明不一致，测试 MUST 失败
