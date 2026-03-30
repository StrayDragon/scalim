# generated-artifacts-manifest Specification

## Purpose
统一“生成物 / 注入区块”的约定与门禁,避免引入额外的 manifest SSOT 与重复维护成本.
## Requirements
### Requirement: generated artifacts MUST follow naming/marker conventions

系统 MUST 通过约定而非额外 manifest 来标识生成物边界:
- 全文件生成物 MUST 使用 `*.gen.*` 命名(例如 `*.gen.md`/`*.gen.json`/`*.gen.yaml`)
- 手工页中的受控注入区块 MUST 使用 `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` markers

#### Scenario: drift checks are driven by generators (no manifest)
- **WHEN** 维护者运行 drift checks
- **THEN** drift checks MUST 直接调用各自生成器的 `--check/--validate` 模式,并在漂移时 fail-fast
- **AND** 不应要求维护者同步维护一份“生成物列表 manifest”

#### Scenario: adding a new generated artifact requires convention compliance
- **WHEN** 新增一个生成物文件
- **THEN** 必须满足上述命名/marker 约定,否则 gate MUST fail-fast
