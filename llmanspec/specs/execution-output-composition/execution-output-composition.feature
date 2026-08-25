# language: zh-CN
# capability: execution-output-composition
# purpose: 支持单次运行的多输出目标组合(多文件或同一容器多逻辑输出),并定义容器命名冲突策略与输出失败策略(`failure_policy`). [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: execution-output-composition

  @req:r41 @human
  场景: 多输出组合
    - 系统 SHALL 允许单次运行定义多个输出目标,每个输出目标拥有独立的字段集合、输出绑定与生命周期,并可同时产出.

  @req:r285 @human
  场景: 容器内多逻辑输出
    - 系统 SHALL 支持将多个输出目标写入同一"容器型"输出(例如同一 workbook 的多个 sheet),并允许为每个目标指定逻辑名称.

  @req:r409 @human
  场景: 容器内命名冲突拒绝
    - 系统 MUST 在同一容器内发现输出名称冲突时直接拒绝,以避免隐式改名造成的隐藏问题.

  @req:r504 @human
  场景: 输出失败策略
    - 系统 SHALL 提供明确的输出失败策略(例如主输出优先或派生输出降级),并保证策略可在运行级别配置.

  @req:r581 @human
  场景: meta/audit error 记录默认不泄露敏感异常信息
    - 当输出组合启用 meta/audit(例如 workbook 内的 Meta/Audit sheet)时,系统 MUST 默认避免将异常的原始 `error_message` 直接写入输出文件. 系统 MUST 至少满足以下行为: - meta/audit MUST 记录 `error_type` - meta/audit 的 `error_message` MUST 默认为安全摘要(例如空/占位/截断预览),不得包含多行与过长文本 - meta/audit SHOULD 记录稳定的 `error_message_hash`(用于对拍与聚类) - 系统 MUST 提供显式开关以允许在"可信环境排障"时写入完整 `error_message` - 该开关 MUST 由 Python/CLI runtime entrypoints 控制 - demand YAML stable authoring surface MUST NOT 提供该字段

  @req:r640 @human
  场景: 多输出组合 MUST compile from a unified destination-binding model
    - 系统 SHALL 从统一的 output target model 编译多输出组合,而不是区分 `container` 与 `books` 两套入口。 统一模型至少包含: - destination binding: `to.file` 或 `to.book` - write policy: `write.*` - layout fields: `fields` 约束: - CSV `OutputSpec` MUST 由 `resources.files + to.file + write` 推导 - Excel `OutputSpec` MUST 由 `resources.books + to.book + to.sheet + write` 推导 - 编译链路 MUST NOT 再依赖 `outputs[*].container`

  @req:r685 @human
  场景: effective header-name validation MUST follow unified write semantics
    - 系统 MUST 在输出编译阶段按统一 `write` 语义判断是否需要启用"有效显示名唯一"校验。 并且该校验 MUST 由 runtime policy 开关 `validate_unique_field_names` 控制: - 默认启用(未显式配置时等价 `true`) - 当其为 `false` 时,系统 MUST 跳过该校验 - 该开关 MUST 由 Python/CLI runtime entrypoints 控制,而不是 demand YAML stable authoring 字段

  @req:r926 @human
  场景: output composition wrappers MUST forward discard
    - 系统 MUST 使 output composition 相关 wrapper sinks（至少 router、tee、counting、以及为 in-memory capture 组装的 tee）在 `discard()` 时向其持有的下游 sink（含 workbook 资源）转发清理；转发失败 MAY best-effort suppress，但 MUST NOT 改为对下游调用成功语义 `close()`。
  @req:r41 @human
  场景: 详情-汇总多目标
    - 必须成立：当 运行配置了详情输出与汇总输出两个目标；那么 系统应同时产出两份结果且互不影响
    当 运行配置了详情输出与汇总输出两个目标
    那么 系统应同时产出两份结果且互不影响

  @req:r41 @human
  场景: 独立输出文件
    - 必须成立：当 多个输出目标绑定到不同的输出位置；那么 系统应分别生成独立输出且互不影响
    当 多个输出目标绑定到不同的输出位置
    那么 系统应分别生成独立输出且互不影响
  @req:r285 @human
  场景: 同一-workbook-多-sheet
    - 必须成立：当 输出目标绑定到同一容器并指定不同逻辑名称；那么 系统应在同一容器中创建并写入多个逻辑输出
    当 输出目标绑定到同一容器并指定不同逻辑名称
    那么 系统应在同一容器中创建并写入多个逻辑输出
  @req:r409 @human
  场景: 逻辑名称冲突
    - 必须成立：当 两个输出目标在同一容器中使用相同逻辑名称；那么 系统应快速失败并返回明确的冲突错误
    当 两个输出目标在同一容器中使用相同逻辑名称
    那么 系统应快速失败并返回明确的冲突错误
  @req:r504 @human
  场景: 派生输出失败
    - 必须成立：当 派生输出失败且策略为"主输出优先"；那么 系统应确保主输出完成且派生输出被标记为失败 **默认策略**: 默认 failure policy 为 `all_fail`: 任一输出失败即认为本次 run 失败(以保证报表包完整性与可对拍一致性) 可选策略 `primary_only`: 仅主输出失败才失败;派生输出失败会被记录(用于 meta/audit)且不阻断主输出
    当 派生输出失败且策略为"主输出优先"
    那么 系统应确保主输出完成且派生输出被标记为失败 **默认策略**: 默认 failure policy 为 `all_fail`: 任一输出失败即认为本次 run 失败(以保证报表包完整性与可对拍一致性) 可选策略 `primary_only`: 仅主输出失败才失败;派生输出失败会被记录(用于 meta/audit)且不阻断主输出
  @req:r581 @human
  场景: 默认仅写安全摘要
    - 必须成立：假如 派生输出(或某个输出目标)在运行中抛出异常且 error_message 含敏感片段(例如 token/SQL/URL)；当 输出组合启用 meta/audit；那么 meta/audit MUST 记录该输出目标的 `error_type`
    假如 派生输出(或某个输出目标)在运行中抛出异常且 error_message 含敏感片段(例如 token/SQL/URL)
    当 输出组合启用 meta/audit
    那么 meta/audit MUST 记录该输出目标的 `error_type`

  @req:r581 @human
  场景: 显式开启后允许写完整-message
    - 必须成立：假如 运行配置显式启用 `include_full_error_message=true`；当 某个输出目标失败并产生异常 message；那么 meta/audit MAY 写入完整 `error_message`
    假如 运行配置显式启用 `include_full_error_message=true`
    当 某个输出目标失败并产生异常 message
    那么 meta/audit MAY 写入完整 `error_message`
  @req:r640 @human
  场景: file-and-book-outputs-compile-through-the-same-target-normal
    - 必须成立：当 一次运行同时包含 `to.file` 与 `to.book` 两类 outputs；那么 系统 MUST 先将它们归一化为统一 target model
    当 一次运行同时包含 `to.file` 与 `to.book` 两类 outputs
    那么 系统 MUST 先将它们归一化为统一 target model
  @req:r685 @human
  场景: duplicate-display-names-are-rejected-when-validate-unique-fi
    - 必须成立：假如 某 file output 会输出表头；当 两个字段的 effective display name 相同；那么 编译 MUST fail-fast
    假如 某 file output 会输出表头
    当 两个字段的 effective display name 相同
    那么 编译 MUST fail-fast

  @req:r685 @human
  场景: duplicate-display-names-are-allowed-when-validate-unique-fie
    - 必须成立：假如 某 file output 会输出表头；当 两个字段的 effective display name 相同；那么 编译 MUST NOT fail-fast on this check
    假如 某 file output 会输出表头
    当 两个字段的 effective display name 相同
    那么 编译 MUST NOT fail-fast on this check

  @req:r926 @human
  场景: router-discard-forwards-to-routes
    - 必须成立：假如 RouterRowSink 持有带 discard 的 route/meta sinks；当 调用 router.discard；那么 MUST 各转发一次；再次 discard MUST 幂等且 MUST NOT close promote
    假如 RouterRowSink 持有带 discard 的 route/meta sinks
    当 调用 router.discard
    那么 MUST 各转发一次；再次 discard MUST 幂等且 MUST NOT close promote
