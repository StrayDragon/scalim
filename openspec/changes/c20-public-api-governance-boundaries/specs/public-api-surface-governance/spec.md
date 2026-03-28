## ADDED Requirements

### Requirement: public facades MUST NOT re-export internal implementation modules

系统 MUST 将 internal 实现细节与稳定公开入口物理隔离.

至少对以下类型的 internal 路径,public facades MUST NOT re-export,且用户材料 MUST NOT 引用：
- `*_internal*` 或 `._internal.*`
- `events._*`
- `dsl.by_yaml.runtime.*`
- 其它在 public API manifest 中未编目的模块路径

#### Scenario: internal re-exports are detected and rejected
- **WHEN** 维护者在 public facade 中新增对 internal 模块的 re-export
- **THEN** public surface gate MUST fail-fast 指出具体模块路径与建议的 facade 迁移方式

### Requirement: stable public surface changes MUST be explicit and auditable

系统 MUST 将 public surface 的新增/删除/重命名视为需要显式决策的变更：
- 任何变更 MUST 同步更新 public API manifest
- 任何变更 MUST 同步更新 public API suite（或等价回归）以覆盖新的公开面

#### Scenario: changing exports requires manifest and suite updates
- **WHEN** 维护者调整任一稳定公开入口模块的 `__all__`
- **THEN** 对应 gate MUST 要求同时更新 manifest 与 suite,否则 fail-fast

