## ADDED Requirements

### Requirement: generated artifacts MUST be declared in a single manifest SSOT

系统 MUST 维护一份机器可读的生成物清单（manifest）,列出仓库中的生成物文件集合与其生成入口,用于 drift checks 的单点 SSOT.

manifest 至少 MUST 包含：
- 生成物路径（或 glob）
- 生成入口（脚本或 `just` 目标）
- drift 校验方式（例如 `git diff` / `--check` 模式）

#### Scenario: drift checks are driven by the manifest
- **WHEN** 维护者运行 drift checks
- **THEN** drift checks MUST 仅从 manifest 读取生成物清单
- **AND** 不应在 `justfile` 中硬编码重复列表

#### Scenario: adding a new generated artifact requires manifest update
- **WHEN** 新增一个生成物文件
- **THEN** 必须同时更新 manifest,否则 gate MUST fail-fast

