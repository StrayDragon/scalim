## Why

随着功能增长，核心实现逐渐出现“维护性债务聚集”信号：

- 超大文件/职责过载（>1k 行）导致改动半径大、review 困难、耦合加深。
- 同名异常类型重复定义、日志体系混用（loggingx / logging / print）、错误对外展示策略分散，导致诊断与安全边界不一致。
- 生成物 drift 检查与门禁清单在 `justfile` 中硬编码，扩展时容易漏、难复用。
- observer dispatch map、内部 utils 等“容易悄悄漂移”的点缺少自动化护栏。

需要把这些维护性问题升级为可执行的治理：明确边界、收敛 SSOT、增加 guardrails，并把重构拆成可回归的小步。

## What Changes

- 拆分巨型模块：按领域+阶段拆分（parse/validate/execute/report 等），降低单点复杂度。
- 异常/日志/错误展示一致化：
  - 同名异常类型收敛到单点；
  - 用户日志与调试日志边界明确（禁止 runtime 混用 print）；
  - 统一“异常→对外消息”的格式化策略（默认 redacted）。
- 生成物门禁 SSOT 化：用 manifest/脚本收敛 drift check 清单，避免 `justfile` 硬编码漂移。
- 增加可维护性 guardrails：事件 dispatch map 完整性检查、`_internal/utils` 治理说明、模块体量阈值守护等。

## Capabilities

### New Capabilities

- `generated-artifacts-manifest`: 生成物清单 SSOT（drift checks 的单点来源）。

### Modified Capabilities

- `module-organization`: 明确模块边界与拆分策略，避免巨型文件持续增长。
- `framework-logging`: 日志输出策略一致化（用户可见日志 vs 调试日志）。
- `error-taxonomy`: 统一错误类型与对外消息策略（`safe_error_message` 全出口一致）。

## Impact

- 受影响代码（SSOT）：`src/scalim/**`（workflow/execute、dsl/by_yaml/workflow_config、execution/output_composition 等热点模块）、`justfile`（drift gate）、相关 scripts/tests。
- 受影响文档：开发者文档（SSOT 在 `docs/doc/dev/**`；生成/注入区块按 `just gen-docs` 刷新）。

