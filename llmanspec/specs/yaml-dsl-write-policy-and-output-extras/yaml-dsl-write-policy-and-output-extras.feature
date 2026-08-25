# language: zh-CN
# capability: yaml-dsl-write-policy-and-output-extras
# purpose: 明确输出资源的四层边界：resources 声明、write_defaults 策略、outputs 内容编排、runtime output extras（meta/audit），并将 write policy 和 extras 迁出 YAML 主线。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-write-policy-and-output-extras

  @req:r133 @human
  场景: `resources` MUST distinguish authoring declarations from runtime overlays
    - 输出资源面 MUST 明确区分“authoring 声明”与“runtime overlay”: - YAML `resources.books/files` MUST 表达基础资源声明 - workflow 资源覆盖与 `RunOverrides.resources` MUST 作为 overlay / deep-merge 生效 - overlay MUST 不改变 `resources` 作为资源 identity 与目标声明面的职责

  @req:r375 @human
  场景: workbook write policy MUST use Python BookWritePolicy as the single SSOT
    - workbook 写策略 MUST 以 Python typed BookWritePolicy（或 ResourcesPolicy.books.*.write）为单一 SSOT: - workbook 级写入行为（mode/align_by/header_policy/on_mismatch/on_conflict）MUST 由 Python runtime policy 表达 - YAML resources.books.*.write_defaults MUST NOT 再作为 authoring SSOT（出现 MUST fail-fast） - outputs[*].write MUST 继续仅承载 output-local 的最小展示/表头 override - outputs[*].write MUST NOT 承载 workbook 级 mode/align_by/header_policy/on_mismatch/on_conflict

  @req:r493 @human
  场景: `meta` and `audit` MUST be runtime output extras instead of YAML authoring field
    - `meta` 与 `audit` MUST 从 YAML 主线迁出,并收敛为 runtime typed output extras: - YAML 主线 MUST 不再把 `meta` / `audit` 作为稳定 authoring 字段 - runtime output extras MUST 明确其 workbook 依赖与输出上下文

  @req:r572 @human
  场景: docs and overrides contracts MUST reflect YAML declaration vs Python write policy
    - 输出相关文档与 typed overrides/policy 契约 MUST 反映以下分工: - resources.books/files = YAML 输出目标声明（id/variant/path） - Python BookWritePolicy = workbook 写策略 SSOT - 系统 MUST NOT 再提供 book cell/sheet 预算（BookBudgetPolicy 已移除；YAML 残留 budget fail-fast） - outputs[*].to/fields/... = output 内容编排 - runtime output extras = meta/audit 等附加产物

  @req:r801 @human
  场景: YAML aggregate 护栏字段已移除并 fail-fast
    - YAML DSL MUST NOT 再提供派生输出的基数护栏 authoring 字段(outputs.<name>.aggregate.{max_groups,max_distinct,distinct_on_overflow}). 当解析到这些残留字段时,系统 MUST fail-fast 报错并给出迁移提示(建议移除该字段,OOM 风险由系统层兜底). YAML DSL MUST NOT 暴露 `dedup_by` / `dedup_by.on_overflow` / `dedup_by.on_conflict`(该能力从未进入 YAML 主线,且 Python IR 侧已移除).

  @req:r803 @human
  场景: YAML score_by_rank 字段已移除并 fail-fast
    - YAML DSL MUST NOT 再提供 score_by_rank authoring 字段. 当解析到残留的 score_by_rank 字段时,系统 MUST fail-fast 报错并给出迁移提示(建议替换为 compute 表达式). compute 表达式 MUST 继续作为聚合后派生字段的通用路径.
  @req:r133 @human
  场景: workflow-and-user-overlays-deep-merge-over-declared-resource
    - 必须成立：假如 某个 demand YAML 声明了基础 `resources.books.report`；当 系统编译并运行该输出；那么 系统 MUST 以基础声明为底并按 overlay / deep-merge 合成最终资源配置
    假如 某个 demand YAML 声明了基础 `resources.books.report`
    当 系统编译并运行该输出
    那么 系统 MUST 以基础声明为底并按 overlay / deep-merge 合成最终资源配置

  @req:r375 @human
  场景: append-via-python-policy
    - 必须成立：假如 两个 demand outputs 绑定同一 book 同一 sheet 且需要 append 合并；当 调用方通过 Python BookWritePolicy(mode=append) 运行 workflow；那么 系统 MUST 按 append 语义合并写入且 MUST NOT 要求 YAML 声明 write_defaults
    假如 两个 demand outputs 绑定同一 book 同一 sheet 且需要 append 合并
    当 调用方通过 Python BookWritePolicy(mode=append) 运行 workflow
    那么 系统 MUST 按 append 语义合并写入且 MUST NOT 要求 YAML 声明 write_defaults
  @req:r493 @human
  场景: audit-sheet-is-configured-by-runtime-output-extras
    - 必须成立：当 用户需要输出 metadata 或 audit workbook sheet；那么 系统 MUST 通过 runtime typed output extras 完成装配
    当 用户需要输出 metadata 或 audit workbook sheet
    那么 系统 MUST 通过 runtime typed output extras 完成装配

  @req:r572 @human
  场景: docs-explain-python-write-ssot
    - 必须成立：当 用户查阅 YAML DSL 输出或 workflow 资源文档；那么 文档 MUST 说明 write_defaults 已迁出 YAML 并由 Python BookWritePolicy 配置，且 book cell/sheet 预算已移除
    当 用户查阅 YAML DSL 输出或 workflow 资源文档
    那么 文档 MUST 说明 write_defaults 已迁出 YAML 并由 Python BookWritePolicy 配置，且 book cell/sheet 预算已移除

  @req:r801 @human
  场景: 残留护栏字段触发报错
    - 必须成立：假如 YAML outputs.<name>.aggregate 中存在 max_groups / max_distinct / distinct_on_overflow 任一字段；当 解析该 YAML；那么 系统 MUST fail-fast 报错,错误信息 MUST 提示该字段已移除并建议删除
    假如 YAML outputs.<name>.aggregate 中存在 max_groups / max_distinct / distinct_on_overflow 任一字段
    当 解析该 YAML
    那么 系统 MUST fail-fast 报错,错误信息 MUST 提示该字段已移除并建议删除

  @req:r803 @human
  场景: 残留 score_by_rank 触发报错
    - 必须成立：假如 YAML outputs.<name>.aggregate.fields.<fid> 中存在 score_by_rank；当 解析该 YAML；那么 系统 MUST fail-fast 报错,错误信息 MUST 提示该字段已移除并建议用 compute 表达式替代
    假如 YAML outputs.<name>.aggregate.fields.<fid> 中存在 score_by_rank
    当 解析该 YAML
    那么 系统 MUST fail-fast 报错,错误信息 MUST 提示该字段已移除并建议用 compute 表达式替代
