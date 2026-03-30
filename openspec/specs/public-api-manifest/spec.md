# public-api-manifest Specification

**状态: ✅ 已实现**

## Purpose
定义 public API 边界治理规则,并在不引入“符号级硬 manifest SSOT”的前提下,确保:
- 稳定入口清晰(约定 + 文档)
- `__all__` 显式治理(避免隐式暴露内部实现)
- 用户材料不得引用内部导入路径(避免把内部实现写进教程/示例/skills)
## Requirements
### Requirement: public entrypoints MUST be explicit via `__all__` + docs
系统 MUST 仍以模块 `__all__` 作为 public export 的符号级契约来源,并通过文档提供用户侧推荐导入的可读投影.

与此前“手工维护推荐导入页”不同,本要求修改为:
- public API 文档页 MUST 由 public API catalog 自动生成,而不是手工维护
- 文档内容 MUST 与 `__all__` 导出面保持一致（通过生成与 drift-check 约束）

#### Scenario: docs stay consistent with `__all__`
- **WHEN** public API 文档生成器从 `__all__` 导出面生成 `.gen.md`
- **THEN** 文档中的模块/导出清单 MUST 与扫描得到的 catalog 一致

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

### Requirement: public API catalog MUST be generated from `__all__` exports
系统 MUST 提供一个可重复运行的生成入口,用于扫描 `src/scalim/**` 下所有声明了 `__all__` 的模块,并汇总其导出符号集合,形成可审计的 public API catalog.

该 catalog MUST 满足:
- 扫描范围默认为 `src/scalim/**`
- MUST 排除 `src/scalim/cli/**` 与 `src/scalim/vendor/**`（以及其它显式排除项）
- 对于 internal 模块（例如 `_internal/` 或 `_*.py`）,其 `__all__` 按治理规则应为空,因此不会扩大 catalog
- 输出 MUST 为确定性产物,并具备可用于 drift-check 的稳定格式

#### Scenario: catalog generation is deterministic and reviewable
- **WHEN** 维护者运行 public API catalog 的生成入口
- **THEN** 系统 MUST 输出一个可审阅的 catalog（包含模块与导出符号清单）
- **AND** 在无代码变更时重复运行 MUST 产生相同结果

### Requirement: public API docs MUST be generated as `.gen.md` from the catalog
系统 MUST 将 public API 导入指南与导出清单改为由 public API catalog 自动生成的 `*.gen.md`,并纳入文档治理与漂移门禁.

该生成物 MUST:
- 文件名包含 `.gen.`（例如 `docs/doc/getting-started/public-api.gen.md`）
- 文件头部包含“自动生成 + 生成入口(脚本或 `just` 目标)”提示
- 由 `just gen-docs`（或其覆盖的受控入口）刷新

#### Scenario: generated public API docs are drift-gated
- **WHEN** 维护者修改 `src/scalim/**` 中的 `__all__` 导出面但未刷新生成文档
- **THEN** drift-check MUST 失败并提示运行生成入口

