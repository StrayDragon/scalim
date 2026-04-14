# yaml-dsl-cli-validation (delta) Specification

## ADDED Requirements

### Requirement: CLI implementation MAY live outside runtime core but MUST preserve validation contracts

系统 MUST 允许将 `PROJECT_CLI_NAME yaml-dsl ...` 的 CLI 实现迁移到独立发行物（例如 `scalim-cli`）以降低 runtime core 的维护负担，但该迁移 MUST 满足：

- CLI 的对外行为契约（退出码、`--json` payload 结构、linter-style 输出格式、workflow validate 合并结构等）MUST 保持与现有规范一致；
- CLI 的校验语义 MUST 委托 `scalim` 内的可复用 service 层（例如 `dsl/yaml_dsl/validation_service.py`），不得在 CLI 包中复制一份语义真相；
- runtime core（`src/IMPL_ROOT/`）MUST 仍可在不安装 CLI 发行物的环境中被 import 并用于 compile/validate/run/workflow。

#### Scenario: runtime imports succeed without CLI distribution
- **GIVEN** 环境未安装 CLI 发行物（例如 `scalim-cli`）
- **WHEN** 调用方导入并使用 runtime 入口（例如 `scalim.dsl.yaml_dsl.run`）
- **THEN** 导入与运行 MUST 成功

