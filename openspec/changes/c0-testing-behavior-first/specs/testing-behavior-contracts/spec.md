## ADDED Requirements

### Requirement: Quality gates MUST prioritize behavior/contract tests over statement coverage

系统的质量门禁（例如 `just qa` / CI）MUST 优先验证“接口行为与契约正确性”，而不是以 100% 语句覆盖率作为主要目标。

该策略至少包括：

- MUST 支持对关键边界建立 contract tests / golden fixtures（可回归、可对拍）。
- MUST 将覆盖率度量从 statement-only 扩展为包含 branch coverage（并允许按模块分阶段收敛阈值）。

#### Scenario: branch coverage is collected in QA runs

- **WHEN** 运行质量门禁（例如 `just qa` 或 CI 对应目标）
- **THEN** 系统 MUST 收集并报告 branch coverage 指标
- **AND** 不得仅依赖 statement coverage 作为唯一覆盖率口径

