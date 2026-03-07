## ADDED Requirements

### Requirement: CI 的默认非 bench 质量门禁必须统一通过 `just qa`
项目的 CI MUST 将 `just qa` 视为默认且权威的非 bench 质量门禁入口,由该入口统一承载 lint、测试、`py36-compat-check`、`py36-typingext-check` 与 frontend 检查.
当这些检查已被 `just qa` 覆盖时,CI MUST NOT 再通过额外 job 或重复 step 重新运行同一组 `py3.6` 兼容检查.

#### Scenario: CI 主 QA job 直接调用 `just qa`
- **WHEN** 审阅仓库默认 CI workflow
- **THEN** 主 QA job MUST 直接执行 `just qa`
- **AND** 不应保留仅重复 `py36-compat-check` 或 `py36-typingext-check` 的独立 job
