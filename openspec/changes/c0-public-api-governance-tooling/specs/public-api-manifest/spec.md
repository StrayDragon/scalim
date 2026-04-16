# public-api-manifest Specification (Delta)

## ADDED Requirements

### Requirement: public API jump-imports MUST be generated from Tier1 curated entrypoints

系统 MUST 提供一个可重复运行的生成入口，用于基于 Tier1 curated entrypoints（`# pragma: scalim-public-api tier1:...`）与各模块字面量 `__all__` 生成一个
“编辑器跳转辅助导入文件”，以便维护者快速了解框架主动 re-export 的稳定入口与符号集合。

该生成物 MUST 满足：

- 输出路径 MUST 为 `.tmp/public_api_jump_imports.py`（属于 dev artifact，禁止提交）。
- 生成逻辑 MUST 采用 AST-only 解析（不 import 目标模块，避免 side effects 与可选依赖影响）。
- 输出 MUST 为确定性产物（无代码变更时重复运行输出一致）。

#### Scenario: maintainer generates jump-imports for Tier1 entrypoints
- **WHEN** 维护者运行 `just gen-public-api-jump-imports`
- **THEN** 系统 MUST 写入 `.tmp/public_api_jump_imports.py`
- **AND** 该文件 MUST 覆盖 Tier1 curated entrypoints 列表中的每个模块，并包含该模块 `__all__` 中的符号导入（忽略非法标识符条目）
