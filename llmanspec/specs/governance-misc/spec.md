---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate governance-misc --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "governance-misc"
purpose: "为“重构分析类文档”提供统一的规范入口与最低要求,确保依赖分析、边界说明、任务拆分、验证口径和约束声明一致,以便在不改动代码的前提下形成可复核的决策依据."
requirements[3]{req_id,title,statement}:
  r1,分析文档最小内容要求,"重构分析文档 SHALL 至少包含模块依赖地图、入口与契约清单、风险点与回滚策略、测试映射与未覆盖风险点,并明确“不得改变对外行为”的约束. 文档 MUST 将任务拆分为可并行子模块,明确输入/输出/验证方式与依赖顺序. 文档 MUST 声明 `__init__.py` 不进行 re-export、运行时保持 Python 3.6 兼容,并包含 Python 最佳实践与类型检查建议."
  r2,yaml_dsl 提案/任务规范,"yaml_dsl 的重构提案 SHALL 给出 Phase 0~Phase 3 的分阶段计划,明确 safe refactor 与 needs review 边界与回滚策略. yaml_dsl 的任务/需求 SHALL 以“一个任务/一个需求”为单位,边界清晰且具备可验证验收条件."
  r3,yaml_dsl 兼容性与不变性约束,"yaml_dsl 的 loader 与 validator SHALL 使用同一 Raw 适配层归一化 YAML 结构;schema 生成结果由元数据驱动并允许更新基线文件. `output.fields` 解析规则(包含 alias/override/歧义报错)、YAML anchor/alias 对象身份语义、resolver allowlist 行为、派生字段 compute 校验与依赖推导均默认保持不变;若某变更需要修改其中任一项,该变更 MUST 在对应 capability 的规范增量中明确新行为并给出兼容性/迁移说明. 对外入口函数签名与返回结构 SHALL 默认保持兼容;内部允许提供简化执行门面. 当确需破坏性变更时(例如移除/重命名对外参数),该变更 MUST 在 `proposal.md` 的 **What Changes** 中以 **BREAKING** 显式标注,并在 `design.md` 与 `tasks.md` 中提供可执行的迁移路径(包含受影响调用点范围与替代 API). 当变更目标明确为“统一公开 API 命名并去除历史歧义”时,系统 MAY 进行破坏性命名收敛,但系统 MUST 满足以下约束: - 在 `proposal.md` 中以 **BREAKING** 明确标注. - 在实现中一次性完成调用方迁移,不保留兼容别名. - 必须覆盖仓内关键业务调用路径. 对于本类变更,迁移完成后旧命名 MUST NOT 继续可用. 为减少“同一件事多种方式”的团队协作成本,对外执行入口 SHOULD 收敛为 `run`, 并通过显式 `outputs/overrides.outputs` 与 `sink=...` 表达输出策略,而不是提供多个 `run_yaml_to_*` 便捷函数. notebooks 示例允许随内部接口调整,不要求向后兼容."
scenarios[12]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,依赖分析可复核,"",审阅者检查重构分析文档,文档包含依赖方向/类型/风险等级标注与关键入口契约
  r1,约束一致性,"",审阅者检查约束声明,"文档明确对外行为不变、禁止 `__init__.py` re-export 且保持 Python 3.6 兼容"
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,分阶段计划可核验,"",审阅者检查提案,每个阶段包含目标、涉及模块、风险、回滚策略与验收标准
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,归一化结果一致,"",loader 与 validator 处理同一份 YAML,归一化后的结构一致且默认值解析不漂移
  r3,对外调用保持兼容,"",现有调用使用 `run` 与 `load_output_config`,参数语义与返回字段保持兼容
  r3,破坏性变更必须显式标注并提供迁移,"",某 change 对 `run` 的参数或返回结构做出破坏性调整,`proposal.md` MUST 包含 **BREAKING** 标注
  r3,关键调用路径同步迁移,"",实施 API 命名收敛变更,关键业务调用路径 MUST 全部使用新命名
  r3,旧命名无残留,"",对仓库进行旧命名扫描,代码路径中不应存在旧 API 命名的调用残留
  r3,非破坏性变更无需迁移段落,"",某 change 不修改对外入口签名与返回结构,`proposal.md` 不应包含与迁移相关的 BREAKING 标注
```
