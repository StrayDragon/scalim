# misc Specification

**状态: ✅ 已实现**
## Purpose
为“重构分析类文档”提供统一的规范入口与最低要求,确保依赖分析、边界说明、任务拆分、验证口径和约束声明一致,以便在不改动代码的前提下形成可复核的决策依据.

## Context
重构往往跨多个模块,需要先形成依赖地图与契约冻结清单,再进入覆盖率提升与实际改动.本 spec 用于承载这些分析文档的最低要求.
## Related Code (as implemented)
- `ARCH.md`
- `openspec/changes/` (refactor change artifacts)
- `justfile` (`type-check`, `lintfix`, `test`, `check`)
- `src/IMPL_ROOT/vendor/compact/typing_extensionsx.py` (typing_extensions compat)
## Requirements
### Requirement: 分析文档最小内容要求
重构分析文档 SHALL 至少包含模块依赖地图、入口与契约清单、风险点与回滚策略、测试映射与未覆盖风险点,并明确“不得改变对外行为”的约束.
文档 MUST 将任务拆分为可并行子模块,明确输入/输出/验证方式与依赖顺序.
文档 MUST 声明 `__init__.py` 不进行 re-export,`src/IMPL_ROOT/` 运行时保持 Python 3.6 兼容,并包含 Python 最佳实践与类型检查建议(含 `typing_extensions` 兼容策略,避免滥用 `getattr/hasattr/setattr`).

#### Scenario: 依赖分析可复核
- **WHEN** 审阅者检查重构分析文档
- **THEN** 文档包含依赖方向/类型/风险等级标注与关键入口契约

#### Scenario: 约束一致性
- **WHEN** 审阅者检查约束声明
- **THEN** 文档明确对外行为不变、禁止 `__init__.py` re-export 且保持 Python 3.6 兼容

### Requirement: yaml_dsl 提案/任务规范
yaml_dsl 的重构提案 SHALL 给出 Phase 0~Phase 3 的分阶段计划,明确 safe refactor 与 needs review 边界与回滚策略.
yaml_dsl 的任务/需求 SHALL 以“一个任务/一个需求”为单位,边界清晰且具备可验证验收条件.

#### Scenario: 分阶段计划可核验
- **WHEN** 审阅者检查提案
- **THEN** 每个阶段包含目标、涉及模块、风险、回滚策略与验收标准

### Requirement: yaml_dsl 兼容性与不变性约束
yaml_dsl 的 loader 与 validator SHALL 使用同一 Raw 适配层归一化 YAML 结构;schema 生成结果由元数据驱动并允许更新基线文件.
`output.fields` 解析规则(包含 alias/override/歧义报错)、YAML anchor/alias 对象身份语义、resolver allowlist 行为、派生字段 compute 校验与依赖推导均默认保持不变;若某变更需要修改其中任一项,该变更 MUST 在对应 capability 的规范增量中明确新行为并给出兼容性/迁移说明.
对外入口函数签名与返回结构 SHALL 默认保持兼容;内部允许提供简化执行门面.
当确需破坏性变更时(例如移除/重命名对外参数),该变更 MUST 在 `proposal.md` 的 **What Changes** 中以 **BREAKING** 显式标注,并在 `design.md` 与 `tasks.md` 中提供可执行的迁移路径(包含受影响调用点范围与替代 API).

当变更目标明确为“统一公开 API 命名并去除历史歧义”时,系统 MAY 进行破坏性命名收敛,但系统 MUST 满足以下约束:
- 在 `proposal.md` 中以 **BREAKING** 明确标注.
- 在实现中一次性完成调用方迁移,不保留兼容别名.
- 必须覆盖仓内关键业务调用路径(包括 `INTEGRATION_APP/execute_batch_tasks/INTEGRATION_DIR/**`).

对于本类变更,迁移完成后旧命名 MUST NOT 继续可用.

为减少“同一件事多种方式”的团队协作成本,对外执行入口 SHOULD 收敛为 `run`,
并通过显式 `outputs/overrides.outputs` 与 `sink=...` 表达输出策略,而不是提供多个 `run_yaml_to_*` 便捷函数.
notebooks 示例允许随内部接口调整,不要求向后兼容.

#### Scenario: 归一化结果一致
- **WHEN** loader 与 validator 处理同一份 YAML
- **THEN** 归一化后的结构一致且默认值解析不漂移

#### Scenario: 对外调用保持兼容
- **WHEN** 现有调用使用 `run` 与 `load_output_config`
- **THEN** 参数语义与返回字段保持兼容

#### Scenario: 破坏性变更必须显式标注并提供迁移
- **WHEN** 某 change 对 `run` 的参数或返回结构做出破坏性调整
- **THEN** `proposal.md` MUST 包含 **BREAKING** 标注
- **AND** `design.md` 与 `tasks.md` MUST 给出迁移步骤与替代用法

#### Scenario: 关键调用路径同步迁移
- **WHEN** 实施 API 命名收敛变更
- **THEN** `INTEGRATION_DIR` 相关调用 MUST 全部使用新命名
- **AND** 不得依赖兼容层运行

#### Scenario: 旧命名无残留
- **WHEN** 对仓库进行旧命名扫描
- **THEN** 代码路径中不应存在旧 API 命名的调用残留

#### Scenario: 非破坏性变更无需迁移段落
- **WHEN** 某 change 不修改对外入口签名与返回结构
- **THEN** `proposal.md` 不应包含与迁移相关的 BREAKING 标注

## Notes
- 本 spec 仅规范“分析文档的最低内容要求”,不要求立即实现代码变更.
- 可在任意重构变更的 `openspec/changes/<id>/` 下引用并遵循本 spec.
