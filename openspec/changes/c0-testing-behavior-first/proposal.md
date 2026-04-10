## Why

当前测试与质量门禁容易被“高语句覆盖率”误导：覆盖率上升并不等价于 bug 被发现（尤其是条件分支、异常路径、状态组合）。同时，当我们准备做大规模重构（例如 IR/plan 静态化、LSP 语义下沉）时，更需要一套围绕**接口行为与契约**的测试策略来提供真实的回归信心，而不是追求 100% statement coverage 的数字目标。

## What Changes

- 将测试目标从“语句覆盖率最大化”调整为“接口行为/契约正确性最大化”：
  - 对关键边界（YAML 解析/校验、静态编译产物、执行计划与依赖图、错误分类）建立 golden fixtures 与 contract tests。
  - 更强调分支覆盖、异常路径与边界条件覆盖（而非行覆盖）。
- 调整覆盖率策略：
  - 在 CI/`just qa` 中支持 `coverage --branch`（branch coverage）作为更接近真实质量的指标。
  - 覆盖率阈值采用**分阶段收敛**（先对关键模块设置门槛，再逐步扩展），避免一次性把历史债务变成推进阻塞。
- 明确测试分层与门禁口径：
  - unit / contract / integration / notebooks 对拍 / perf-regression（基线）等类别，分别定义“该测什么、不该测什么”与运行入口。

## Capabilities

### New Capabilities

- `testing-behavior-contracts`: 为核心 API/边界建立行为契约测试的规范与最小样例集（含 golden fixtures 组织方式与更新流程）。
- `coverage-branch-gates`: 在质量门禁中引入 branch coverage（可按模块/目录设置阈值），并提供增量收敛策略。

### Modified Capabilities

- `testing-quality`: 将质量度量从“statement 覆盖率优先”调整为“行为契约 + 分支覆盖优先”，并明确何时使用 notebooks/集成对拍作为回归基线。
- `tests-domain-suites`: 现有测试套件的组织方式与职责边界需要随之更新（例如哪些 suite 属于 contract/integration）。

## Impact

- 工程入口：
  - `just qa`、CI 流程、pytest/coverage 配置（例如 `pyproject.toml` 或对应配置文件）需要按新口径调整。
- 测试代码组织：
  - 可能需要新增/重组 `tests/` 下的 suite（例如 `tests/contract/**`、`tests/integration/**`）与 fixtures 目录（例如 `tests/fixtures/**`）。
- 文档与规范：
  - 若对外公开测试/质量策略，需要在 `openspec/specs/testing-quality/` 等规范中同步更新（SSOT 为 `openspec/specs/**`）。
- 风险（概述）：
  - 引入 branch coverage 可能会暴露大量历史遗漏分支 → 采用分阶段阈值与目录白名单策略缓解。
  - golden fixtures 的维护成本与“更新即通过”的风险 → 需要明确审批/更新准则（例如仅当需求变更或已确认修复 bug 时更新）。
