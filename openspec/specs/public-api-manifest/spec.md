# public-api-manifest Specification

**状态: ✅ 已实现**

## Purpose
定义 public API 边界治理规则,并在不引入“符号级硬 manifest SSOT”的前提下,确保:
- 稳定入口清晰(约定 + 文档)
- `__all__` 显式治理(避免隐式暴露内部实现)
- 用户材料不得引用内部导入路径(避免把内部实现写进教程/示例/skills)

## Requirements

### Requirement: public entrypoints MUST be explicit via `__all__` + docs

系统 MUST 通过 `__all__` 明确 public export,并在文档中明确推荐导入入口.

约束来源(约定优先):
- `docs/doc/getting-started/public-api.md` 作为推荐入口的“人类可读 SSOT”
- `scripts/check-api-surface-governance.py --check` 作为 `__all__` 治理门禁
- `tests/test_example_public_api_suite.py` 作为稳定入口的最小可运行回归

#### Scenario: `__all__` governance prevents accidental export
- **WHEN** 贡献者在模块中引入内部实现(例如 `_name`/`_internal`/`_*.py`)
- **THEN** `scripts/check-api-surface-governance.py --check` MUST 立即报错

### Requirement: user-facing materials MUST NOT import internal paths

系统 MUST 将 docs/skills/examples 视为“用户可见材料”,并禁止其导入内部实现路径(约定: `._internal` 或 `._foo` 均视为内部实现).

#### Scenario: internal-path imports are rejected in user-facing materials
- **WHEN** docs/skills/examples 中出现 `_internal` 或其它未编目的内部实现导入路径
- **THEN** `scripts/check-user-material-import-boundaries.py --check` MUST 立即报错 并提示替代的稳定导入路径

### Requirement: hard manifest SSOT MUST NOT be required

系统 MUST NOT 要求维护者手工维护“符号级 manifest”才能通过 public API 治理门禁(维护成本高,且容易把简单约定复杂化).

#### Scenario: public API gates do not rely on a symbol-level manifest
- **WHEN** 贡献者为 public facade 模块调整 `__all__`(新增/删除/重命名符号)
- **THEN** 治理门禁 MUST 仅依赖 `__all__` 治理脚本 + 示例回归通过
- **AND** 不应要求同步更新某个符号级 manifest 文件才能通过 CI
