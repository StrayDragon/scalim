## ADDED Requirements

### Requirement: a machine-readable public API manifest MUST exist and MUST be the SSOT

系统 MUST 维护一份机器可读的 public API manifest,作为“稳定公开入口”的单一事实来源（SSOT）.

manifest 至少 MUST 表达：
- 稳定公开入口模块列表（module import path）
- 每个模块允许导出的符号白名单（等价于该模块 `__all__`）
- 允许被 docs/skills/examples 引用的导入路径集合（curated entrypoints）

manifest MUST 具备以下性质：
- 可被脚本/CI 解析（例如 JSON/YAML/TOML）
- 内容按稳定排序输出（避免漂移）
- 变更可审计（新增/删除/重命名导出必须显式修改 manifest）

#### Scenario: manifest is used to validate __all__ exports
- **WHEN** 维护者运行 public surface gate
- **THEN** gate MUST 按 manifest 校验每个稳定公开入口模块的 `__all__`
- **AND** 任意缺失/新增导出 MUST fail-fast

### Requirement: public-facing materials MUST import only from curated entrypoints

系统 MUST 将 docs/skills/examples 视为“用户可见材料”,并要求其导入路径仅来自 manifest 的 curated entrypoints.

#### Scenario: internal-path imports are rejected in user-facing materials
- **WHEN** docs/skills/examples 中出现 `_internal` 或其它未编目的内部实现导入路径
- **THEN** gate MUST fail-fast 并提示替代的稳定导入路径

