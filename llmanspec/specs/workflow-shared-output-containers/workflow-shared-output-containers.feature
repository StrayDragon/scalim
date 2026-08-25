# language: zh-CN
# capability: workflow-shared-output-containers
# purpose: 定义 workflow 共享输出容器的资源声明、写入节点、确定性顺序、追加/合并语义、原子提交、可观测性及并发安全契约。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: workflow-shared-output-containers

  @req:r97 @human
  场景: workflow YAML exposes a stable authoring surface for shared resources and write
    - 系统 MUST 为共享输出容器提供可实现、可校验的 workflow YAML authoring surface,并将“写入意图”从 workflow `writes` 收敛为 demand outputs 的 IO 绑定(由 workflow 编译期推导写入节点): - 资源声明: - `workflow.resources.books.<book_id>` MUST 为 mapping 且 MUST 满足 `yaml-dsl-books-resources` 对 book 的约束 - 写入意图: - workflow YAML MUST NOT 再暴露已移除的 workflow-level 写入 intents authoring surface - 系统 MUST 从每个 run 引用的 demand YAML 中读取 `outputs[*].to` / `outputs[*].write` 推导等价的写入节点集合 迁移约束(破坏性变更): - legacy workflow resource groups(workbooks/csvs/sheetbooks) MUST 被拒绝并给出迁移提示(迁移到 `workflow.resources.books`) - 已移除的 workflow-level 写入 intents MUST 被拒绝并给出迁移提示(迁移到 demand outputs 的 `to/write` 绑定)

  @req:r339 @human
  场景: workflow declares shared output resource identity at workflow scope
    - 系统 MUST 允许在 workflow 层声明共享输出资源 identity（books）并由 runtime 管理生命周期: - 资源声明 MUST 位于 workflow.resources.books - 每个资源 MUST 具备稳定 id 与 variant 对应的必要 path/export 声明 - write 策略 MUST 来自 Python BookWritePolicy（不是 YAML write_defaults） - 系统 MUST NOT 再提供 book cell/sheet 内存预算（BookBudgetPolicy 已移除） - 系统 MUST 静态校验资源 identity 声明（id 唯一、必填 path 等）

  @req:r461 @human
  场景: shared output is written via explicit workflow write nodes
    - 系统 MUST 将“写入共享 book 资源”的动作建模为 workflow 的显式节点类型,而不是 demand 的隐式后处理: - 系统 MUST 支持至少两类写入节点语义: - `write_sheet`(写入/覆盖某个 sheet; 对应 `mode=sheet`) - `append_sheet`(追加写入某个 sheet; 对应 `mode=append`,具备字段对齐与 header 策略) - workflow YAML authoring surface 不再手写 write intents,但编译后语义 MUST 等价于显式 write nodes - 写入节点 MUST 消费上游 demand 节点的 output artifacts；该 artifact 可以是文件路径 output,也可以是 workflow-managed 的内存表格 artifact(例如 `InMemoryRows` 或等价结构) - 当写入节点消费的是 workflow-managed 内存 artifact 时,消费完成后系统 MUST 参与该 artifact 的最终消费者释放流程

  @req:r546 @human
  场景: writes to shared resources are deterministic and serialized
    - 系统 MUST 定义确定性写入顺序,且 MUST NOT 依赖并发完成顺序: - 对同一共享 book 资源的写入 MUST 互斥/串行化 - 写入顺序 MUST 由声明顺序决定: - 以 workflow YAML `runs` 列表顺序为一级 SSOT - 以每个 demand YAML 的 `outputs` 列表顺序为二级 SSOT

  @req:r616 @human
  场景: append/merge semantics are explicit via Python write policy
    - 当多个节点写入同一个 sheet 或以 append 方式合并时,系统 MUST 定义明确且可测试的合并语义: - 字段对齐、header 策略、mismatch/conflict 策略 MUST 明确可配置 - 上述策略的 SSOT MUST 为 Python BookWritePolicy（缺省 builtin defaults） - 策略 MUST NOT 再通过 YAML resources.books.*.write_defaults 或已移除的 workflow writes 表达

  @req:r665 @human
  场景: shared resources commit atomically at workflow end
    - 系统 MUST 定义共享资源的落盘/提交语义,避免“部分写入但语义不清”的灰区: - 共享资源 MUST 在 workflow 成功结束后统一 commit,并以原子方式落盘(只保存一次/原子替换) - 当 workflow 失败时,系统 MUST discard 未提交的共享资源（v0 不支持 partial commit）

  @req:r707 @human
  场景: shared resource lifecycle MUST be observable
    - 系统 MUST 为共享资源生命周期提供可观测事件/钩子点,以便排障与可视化: - 系统 MUST 发出以下事件类型: - `workflow_resource_create` - `workflow_resource_write` - `workflow_resource_commit` - `workflow_resource_discard` - 事件 MUST 复用 workflow 归因字段(例如 `workflow_exec_id` / `workflow_node_id`)

  @req:r741 @human
  场景: shared resource plan creation MUST be atomic and joinable within a workflow exec
    - 当 workflow 并发执行多个 nodes 且多个写入节点引用同一个共享 book 资源时,系统 MUST 确保该资源在一次 workflow 执行内仅创建一个 plan,并允许并发写入方 join 到同一 plan： - 对同一 `resource_id` 的 “get-or-create” MUST 原子（并发首次命中不得产生多个 plan）。 - 该资源的写锁获取 MUST 与该 plan 绑定且在一次 workflow 执行内只发生一次；同一 workflow 内的其它并发写入 MUST join 而不是被误判为并发写者。 - 最终 commit MUST 包含所有写入方产生的写入意图（不得丢写）。

  @req:r770 @human
  场景: joinable get-or-create 的等待诊断
    - 系统 SHALL 为共享资源的 joinable get-or-create 提供可选的 wait diagnostics,使 waiter 等待过程可观测且可定位. 该诊断配置 MUST 作为 workflow-level SSOT 暴露(例如 `workflow.options.resources_wait`),并贯穿 YAML→IR→runtime. 约束: - 诊断配置 MUST 包含 `diagnostics.enabled`(默认 false) - 当 `diagnostics.enabled=true` 时,诊断配置 MUST 包含 `warn_after_s`(首次告警阈值)和可选的 `repeat_every_s`(重复告警间隔) - 告警 MUST 包含: `resource_id`、owner 线程标识、waiter 线程标识、已等待时长 - 当启用 `capture_owner_callsite=true` 时,告警 SHOULD 额外包含 owner callsite(用于定位卡住的创建点) - 告警 MUST 走 instrumentation event 或 warning logger,不得污染正常输出 - 默认行为 MUST 为禁用(仅在 `diagnostics.enabled=true` 时输出告警)

  @req:r149 @human
  场景: joinable get-or-create 的可选超时
    - 系统 MUST 为共享资源的 joinable get-or-create 提供 max wait / fail-fast 能力,以避免并发场景无限等待导致 workflow hang. 约束: - 超时后 MUST 以 `WorkflowWriteError` 失败,错误消息包含 resource_id、owner 线程标识、已等待时长与 max_wait_s - 默认策略 MUST 为启用超时且 `max_wait_s=600`(BREAKING: 不再允许无限等待作为默认) - 超时值 MUST 可配置(优先通过 workflow-level 配置 `workflow.options.resources_wait.max_wait_s`) - 若显式将 `max_wait_s` 配置为 `0` 或负数,MUST 被拒绝并给出配置错误

  @req:r170 @human
  场景: commit_all/discard_all 与 inflight 并发交错语义
    - 系统 MUST 在 `commit_all()`/`discard_all()` 执行时显式处理与 inflight 创建的并发交错,并采用 **drain** 策略: - commit/discard 在开始前 MUST 等待所有 inflight 创建完成,保证不会"漏 commit / 漏 discard" 约束: - drain 等待 MUST 复用 wait diagnostics(含 warn-after/timeout)

  @req:r189 @human
  场景: workflow workbook exports MUST escape Excel formulas by default
    - 当 workflow 通过共享 pathful xlsx book（`resources.books.<id>.xlsx.path`）导出 `.xlsx` 时,系统 MUST 默认保留所有字符串 cell 值原样写出,不得执行公式前缀转义。 防护模式（不可信输入显式收紧）： - 若 effective book 配置 `allow_formulas=false`,系统 MUST 对所有字符串 cell 值执行公式前缀转义,以避免 `Excel` 将其解析为公式。

  @req:r207 @human
  场景: workflow workbook resource authoring surface MUST support allow_formulas
    - 系统 MUST 支持 workflow YAML 的 book 资源声明包含可选字段 `workflow.resources.books.<book_id>.xlsx.allow_formulas`： - 该字段 MUST 为 bool - 缺省时 MUST 等价于 `true`

  @req:r223 @human
  场景: workflow MUST precheck Excel output-path collisions across books deterministical
    - 当 workflow 声明多个 `xlsx` 导出路径时,系统 MUST 在“写入发生前”检测潜在的路径冲突,并采用确定性规则 fail-fast: - 若两个 book 的 effective 导出路径相同(同一路径),系统 MUST 拒绝执行并报告冲突的 book ids 与 path - 路径判定 MUST 基于 `expanduser + resolve(strict=False)` 的归一化绝对路径 动态路径约束: - 若 book path 由 `{$init_var: ...}` 注入,系统 MUST 使用渲染后的最终路径参与冲突判断 - 对依赖 `$ctx` 的注入(compile-on-ready) MUST 在该节点物化编译后,仍在实际写入前做最终冲突预检查

  @req:r236 @human
  场景: commit order MUST NOT depend on thread scheduling
    - 当 workflow 在并发模式执行时,系统 MUST 禁止将共享资源（csv/workbook/sheetbook）的最终写入顺序绑定到线程调度或节点完成时序. 系统 MUST 为每条写入意图记录稳定的 `decl_order`（声明顺序序号）,并在 commit 阶段按 `decl_order` 稳定排序后写出.

  @req:r247 @human
  场景: workbook/sheetbook sheet order MUST be stable
    - 系统 MUST 定义 workbook/sheetbook 的 sheet 顺序策略,且不得依赖“并发首次创建时 append”导致的漂移.

  @req:r255 @human
  场景: shared outputs MUST commit into staging and publish on success
    - 系统 MUST 将 workflow 共享输出容器（csv/workbook/sheetbook）的落盘语义收敛为 staging → publish: - commit 阶段 MUST 写入 staging 唯一路径（不得直接写入最终导出路径） - workflow 成功结束后 MUST 覆盖发布到最终导出路径（原子 replace） - 默认清理策略 MUST 为: - success: 清理 staging exec dir - failure: 保留 staging（便于排障） staging 路径布局约束: - 对最终路径 `final_path`,staging MUST 为 `<final_dir>/<dir_name>/<workflow_exec_id>/<filename>` - `dir_name` 由 `workflow.options.output_staging.dir_name` 提供或缺省为 `.scalim-staging`

  @req:r262 @human
  场景: workflow controller MUST be the sole writer of workflow-managed shared state
    - 当 workflow 以并发模式执行（`max_concurrency > 1`）时，系统 MUST 将所有 workflow-managed 的共享可变状态更新收敛到单一 controller（单写者/actor）执行上下文中： - `WorkflowArtifactsDirectory` 的 publish/get/discard - `WorkflowCtxStore` 的 publish/resolve - `WorkflowResourceManager` 的 create/write/commit/discard 并发线程（worker）MUST 仅负责纯计算（例如执行 `run_ir`）并将结果回传给 controller；worker MUST NOT 直接写入上述共享状态。

  @req:r269 @human
  场景: WorkflowArtifactsDirectory MUST fail-fast on any non-controller thread write pat
    - `WorkflowArtifactsDirectory` 是 workflow-managed 的共享可变状态. 所有会写内部状态的 API MUST 被视为 controller-only writer,包括: - `publish` / `discard` - in-memory artifact cleanup helpers(例如 `discard_in_memory_*`、`discard_all_in_memory_*`、`discard_all_in_memory_rows`) 任一非 controller 线程(worker)调用上述 writer API MUST 被视为实现错误,并 MUST fail-fast(例如抛出 `RuntimeError`),而不是静默写入共享状态.

  @req:r379 @human
  场景: The single-writer contract MUST be consistently enforced across all artifacts cl
    - 单写者契约 MUST NOT 仅在“主入口 API”上部分生效,而留下 helper 方法的未加固写路径. 任何会写内部 dict 的 artifacts helper MUST 具备与 `publish/discard` 等价的 owner-thread enforcement.

  @req:r385 @human
  场景: workflow shared resources MUST publish into versioned output roots and update ma
    - 当 workflow 最终 commit 共享输出资源（books/files）时，系统 MUST 按版本化输出（D-2）协议发布： - 产物 MUST 写入 `<root>/versions/<workflow_exec_id>/...` - 系统 MUST 写入 `<root>/versions/<workflow_exec_id>/manifest.json` - 系统 MUST 原子更新 `<root>/manifest/latest.json` - 系统 MUST NOT 在产物路径旁生成 `<final_path>.scalim.lock`

  @req:r389 @human
  场景: workflow 写入节点按 field_id 对齐展示名仅用于表头行
    - workflow 共享输出容器的写入节点进行字段对齐时,MUST 基于唯一 field_id 而非展示列名;可重复的展示列名 MUST 仅用于表头行输出,不得参与列对齐映射。该约束 MUST 统一适用于所有共享输出容器类型(pathful workbook、csv/file、pathless sheetbook)。具体地:workflow-managed 中间工件(InMemoryCsv 与 InMemoryRows)的 header MUST 为 field_id;可重复的展示名经独立 export_header 透传,仅在导出表头行使用;列对齐映射 MUST 始终在唯一 field_id 上运行,不得因展示名重复而坍缩。

  @req:r393 @human
  场景: xlsx spreadsheet books MUST use tabular managed-artifact pipeline without FieldValue gate
    - When a workflow-managed demand output is bound to a shared pathful or pathless xlsx book, the system MUST materialize that output as `MANAGED_ARTIFACT_KIND_ROWS` (`InMemoryRows`) and MUST set the composed `OutputSpec.format` to `excel`. The pipeline MUST pass cell values through without first stringifying via `InMemoryCsvSink` / `_normalize_csv_value()` for those books, and MUST NOT apply a `FieldValue` closed-set runtime gate at the ROWS intermediate. Temporal and other cell objects MUST be preserved as-is in the tabular bus (including timezone-aware instances); the system MUST NOT clear `tzinfo` or otherwise rewrite user temporal values for Excel compatibility. Write compatibility MUST be enforced at the Excel/workbook/sheetbook sink boundary by default (or via Python opt-in precheck against the sink accept set). Write nodes for `resource_type=book` MUST resolve inputs via `resolve_workflow_input_tabular` (or equivalent) from the ROWS artifact.

  @req:r24 @human
  场景: ROWS managed plans MUST NOT eagerly duplicate CSV artifacts
    - For `ManagedArtifactPlan` with `kind=ROWS`, `_collect_managed_artifact_outputs()` MUST NOT call `to_csv_artifact()` / `in_memory_rows_to_in_memory_csv()` eagerly. This MUST apply to both pathful and pathless managed book outputs. `in_memory_rows_to_in_memory_csv()` MUST remain available as an explicit public utility. This requirement does NOT obligate the runtime to auto-derive CSV artifacts when a CSV consumer exists; any future consumer-driven derivation MUST be an explicit conversion (never unconditional eager duplication) and is out of scope for the change that introduces this requirement.

  @req:r25 @human
  场景: pathful workbook plans MUST own materialized typed row segments
    - `resources_workbook` MUST store sheet segments as owned typed rows (`List[List[FieldValue]]`) with `producer_node_id`, `decl_order`, and `header_policy`, materialized at `apply_workbook_sheet` / `apply_workbook_append` via `read_tabular_header` + alignment mapping + `materialize_aligned_tabular_rows`. Segments MUST NOT retain a parallel CSV input reference as the SSOT for commit. Commit/export MUST iterate owned segment rows and apply `escape_excel_formula` only to `str` values. `InMemoryCsv` and CSV file paths remain valid `WorkflowTabularInput` adapters at apply time, but after apply the plan SSOT is the materialized typed rows. Header/export_header/field_id alignment semantics MUST remain equivalent to the previous workbook behavior aside from value typing.

  @req:r26 @human
  场景: shared book pipeline MUST release demand artifacts and plan segments after final consumers
    - 在保持成功后统一 commit/失败 discard 的前提下,系统 MUST 降低共享 book 路径的不必要内存双驻留: - 对 managed tabular artifact 的消费者闭包仅包含仍待执行且输入解析到该 artifact 的 workflow write nodes - book_sheet_rows(或等价)读取的是 book plan 而非 demand artifact;其可见性 MUST 由 plan 生命周期保证(不得在 commit/discard 前清空 plan) - 不计入 workflow 结束后的用户侧 Python 引用与非 workflow-managed 捕获 - 当 write node 已成功将 artifact 物化进 book plan且该 artifact 已无剩余 write consumers 时,系统 MUST 释放 demand 侧内存副本 - commit_all 成功或 discard_all 完成之后,系统 MUST 释放 plan 持有的 segment 行数据(清空 segments 和/或丢弃 plan) - 释放 MUST NOT 破坏 book_sheet_rows 基于 plan 的可见性语义 - 释放点 MUST 通过既有 diagnostics/结构化日志可诊断(原因枚举至少含 no_remaining_consumers|commit|discard);MUST NOT 引入 YAML 开关;MUST NOT 以本需求强制新增公开 Event 类型

  @req:r27 @human
  场景: pathless book cell/sheet budget MUST NOT be provided
    - 系统 MUST NOT 再为 pathless/pathful book 提供进程内 cell/sheet 预算护栏（BookBudgetPolicy / max_sheets / max_total_cells 已移除）: - YAML 中残留 budget 字段 MUST fail-fast 并提示删除该字段（内存风险交宿主资源限制） - Python 侧 MUST NOT 再暴露 BookBudgetPolicy 或等价预算配置 - 高内存风险由宿主系统层（cgroup / OOM killer 等）兜底
  @req:r97 @human
  场景: shared-output-authoring-surface-passes-schema-validation
    - 必须成立：当 workflow YAML 包含 `workflow.resources.books` 且不包含已移除的 workflow-level 写入 intents；那么 schema-only 校验 MUST 通过
    当 workflow YAML 包含 `workflow.resources.books` 且不包含已移除的 workflow-level 写入 intents
    那么 schema-only 校验 MUST 通过

  @req:r339 @human
  场景: identity-without-write-defaults
    - 必须成立：假如 workflow YAML 仅声明 books id/variant/path；当 配合 builtin 或 Python BookWritePolicy 运行；那么 共享资源生命周期 MUST 正常 create/write/commit
    假如 workflow YAML 仅声明 books id/variant/path
    当 配合 builtin 或 Python BookWritePolicy 运行
    那么 共享资源生命周期 MUST 正常 create/write/commit
  @req:r461 @human
  场景: write-nodes-depend-on-demand-outputs
    - 必须成立：假如 write_sheet 节点消费 run A 的 output `detail`；当 workflow 执行；那么 系统 MUST 在 run A 成功完成并产生该 output 后才允许 write_sheet 执行
    假如 write_sheet 节点消费 run A 的 output `detail`
    当 workflow 执行
    那么 系统 MUST 在 run A 成功完成并产生该 output 后才允许 write_sheet 执行

  @req:r461 @human
  场景: write-nodes-can-consume-workflow-managed-in-memory-artifacts
    - 必须成立：假如 write_sheet 节点消费 run A 的 output `detail`；当 workflow 执行；那么 write_sheet MUST 无需依赖临时 CSV 文件路径即可完成写入
    假如 write_sheet 节点消费 run A 的 output `detail`
    当 workflow 执行
    那么 write_sheet MUST 无需依赖临时 CSV 文件路径即可完成写入
  @req:r546 @human
  场景: writes-to-a-shared-book-are-deterministic
    - 必须成立：假如 两个 runs 都绑定到同一个共享 book 的不同 sheets；当 workflow 在并发模式下执行多次；那么 对共享资源的写入顺序 MUST 可复现,且结果 MUST 等价
    假如 两个 runs 都绑定到同一个共享 book 的不同 sheets
    当 workflow 在并发模式下执行多次
    那么 对共享资源的写入顺序 MUST 可复现,且结果 MUST 等价

  @req:r616 @human
  场景: append-policy-from-python
    - 必须成立：假如 Python BookWritePolicy(mode=append,header_policy=once)；当 两 runs 写入同一 book 同一 sheet；那么 最终 sheet MUST 按 append 语义合并且 YAML 无需 write_defaults
    假如 Python BookWritePolicy(mode=append,header_policy=once)
    当 两 runs 写入同一 book 同一 sheet
    那么 最终 sheet MUST 按 append 语义合并且 YAML 无需 write_defaults
  @req:r665 @human
  场景: failed-workflow-does-not-leave-partial-committed-output
    - 必须成立：假如 workflow 包含共享 book 且其中部分写入节点已执行；当 workflow 结束；那么 系统 MUST 不产生“已提交但不完整”的最终 xlsx 文件(默认 discard)
    假如 workflow 包含共享 book 且其中部分写入节点已执行
    当 workflow 结束
    那么 系统 MUST 不产生“已提交但不完整”的最终 xlsx 文件(默认 discard)
  @req:r707 @human
  场景: resource-lifecycle-events-are-joinable
    - 必须成立：假如 workflow 声明共享 book 资源并执行写入；当 workflow 成功 commit 或失败 discard 该资源；那么 observer MUST 能观测到对应的 commit/discard 事件
    假如 workflow 声明共享 book 资源并执行写入
    当 workflow 成功 commit 或失败 discard 该资源
    那么 observer MUST 能观测到对应的 commit/discard 事件
  @req:r741 @human
  场景: concurrent-writes-to-a-shared-book-join-a-single-plan
    - 必须成立：假如 workflow 并发执行两个 nodes A/B；当 多次执行该 workflow；那么 系统 MUST 不得因“重复获取写锁”而 fail-fast
    假如 workflow 并发执行两个 nodes A/B
    当 多次执行该 workflow
    那么 系统 MUST 不得因“重复获取写锁”而 fail-fast
  @req:r770 @human
  场景: waiter-等待超过阈值时产生诊断告警
    - 必须成立：假如 wait diagnostics 启用且 `warn_after_s=5.0`；当 waiter 等待 owner 创建资源超过 5 秒；那么 系统 MUST 发出包含 resource_id/owner_thread/waiter_thread/wait_s 的告警
    假如 wait diagnostics 启用且 `warn_after_s=5.0`
    当 waiter 等待 owner 创建资源超过 5 秒
    那么 系统 MUST 发出包含 resource_id/owner_thread/waiter_thread/wait_s 的告警
  @req:r149 @human
  场景: owner-卡死导致-waiter-超时
    - 必须成立：假如 max_wait_s 配置为 60 秒；当 owner 线程创建资源超过 60 秒未完成；那么 waiter MUST 以包含诊断信息的 `WorkflowWriteError` 失败
    假如 max_wait_s 配置为 60 秒
    当 owner 线程创建资源超过 60 秒未完成
    那么 waiter MUST 以包含诊断信息的 `WorkflowWriteError` 失败

  @req:r149 @human
  场景: default-timeout-is-enforced
    - 必须成立：假如 未显式配置 max_wait_s；当 owner 线程创建资源超过默认超时；那么 waiter MUST fail-fast,而不是无限等待
    假如 未显式配置 max_wait_s
    当 owner 线程创建资源超过默认超时
    那么 waiter MUST fail-fast,而不是无限等待
  @req:r170 @human
  场景: commit-all-与-inflight-创建并发时-drain
    - 必须成立：假如 采用 drain 策略；当 某线程正在 inflight 创建资源,另一线程调用 `commit_all()`；那么 `commit_all()` MUST 等待 inflight 创建完成后再 commit 所有资源
    假如 采用 drain 策略
    当 某线程正在 inflight 创建资源,另一线程调用 `commit_all()`
    那么 `commit_all()` MUST 等待 inflight 创建完成后再 commit 所有资源
  @req:r189 @human
  场景: allow-formulas-is-true-by-default-and-preserves-raw-strings
    - 必须成立：假如 workflow 声明 book 资源 `report` 且未显式设置 `allow_formulas`；当 某个写入节点将字符串 `\"=1+1\"` 写入该 book；那么 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"=1+1\"`
    假如 workflow 声明 book 资源 `report` 且未显式设置 `allow_formulas`
    当 某个写入节点将字符串 `\"=1+1\"` 写入该 book
    那么 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"=1+1\"`

  @req:r189 @human
  场景: allow-formulas-false-escapes-formula-like-strings
    - 必须成立：假如 workflow 声明 book 资源 `report` 且设置 `allow_formulas=false`；当 某个写入节点将字符串 `\"=1+1\"` 写入该 book；那么 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"'=1+1\"`
    假如 workflow 声明 book 资源 `report` 且设置 `allow_formulas=false`
    当 某个写入节点将字符串 `\"=1+1\"` 写入该 book
    那么 导出的 `.xlsx` 中对应单元格值 MUST 为 `\"'=1+1\"`
  @req:r207 @human
  场景: book-allow-formulas-passes-schema-validation
    - 必须成立：当 workflow YAML 声明 `workflow.resources.books.report.allow_formulas=false`；那么 schema-only 校验 MUST 通过
    当 workflow YAML 声明 `workflow.resources.books.report.allow_formulas=false`
    那么 schema-only 校验 MUST 通过
  @req:r223 @human
  场景: duplicate-xlsx-export-paths-are-rejected-deterministically
    - 必须成立：假如 workflow 声明两个 book: `a` 与 `b`；当 workflow 被编译/校验；那么 系统 MUST fail-fast 并报告冲突路径与 book ids
    假如 workflow 声明两个 book: `a` 与 `b`
    当 workflow 被编译/校验
    那么 系统 MUST fail-fast 并报告冲突路径与 book ids
  @req:r236 @human
  场景: concurrent-appends-preserve-declaration-order
    - 必须成立：假如 两个并发 runs 对同一共享 csv 资源 append 写入；当 workflow 在并发模式下重复执行多次；那么 最终落盘 csv 的段顺序 MUST 始终与 YAML 声明顺序一致
    假如 两个并发 runs 对同一共享 csv 资源 append 写入
    当 workflow 在并发模式下重复执行多次
    那么 最终落盘 csv 的段顺序 MUST 始终与 YAML 声明顺序一致
  @req:r247 @human
  场景: sheet-order-is-stable-across-concurrent-runs
    - 必须成立：当 并发执行多个写入不同 sheets 的 write intents；那么 导出的 workbook/sheetbook 内 sheet 顺序 MUST 可复现
    当 并发执行多个写入不同 sheets 的 write intents
    那么 导出的 workbook/sheetbook 内 sheet 顺序 MUST 可复现
  @req:r255 @human
  场景: publish-overwrites-final-path-on-success
    - 必须成立：假如 workflow 成功结束且存在 staged output；当 执行 publish；那么 最终导出路径 MUST 被原子覆盖为 staged output 的内容
    假如 workflow 成功结束且存在 staged output
    当 执行 publish
    那么 最终导出路径 MUST 被原子覆盖为 staged output 的内容
  @req:r262 @human
  场景: worker-threads-do-not-mutate-workflow-managed-state
    - 必须成立：假如 workflow 启用并发执行（`max_concurrency=2`）；当 两个 demand nodes 并发运行并产生 outputs；那么 系统 MUST 仅在 controller 上下文中发布 artifacts/ctx/resource 写入
    假如 workflow 启用并发执行（`max_concurrency=2`）
    当 两个 demand nodes 并发运行并产生 outputs
    那么 系统 MUST 仅在 controller 上下文中发布 artifacts/ctx/resource 写入
  @req:r269 @human
  场景: worker-misuse-of-in-memory-discard-helpers-fails-fast
    - 必须成立：假如 workflow 启用并发执行（`max_concurrency > 1`）；当 worker 线程调用 `WorkflowArtifactsDirectory` 的 in-memory discard/cleanup helper；那么 调用 MUST fail-fast(例如抛出 `RuntimeError`),而不是静默写入共享状态
    假如 workflow 启用并发执行（`max_concurrency > 1`）
    当 worker 线程调用 `WorkflowArtifactsDirectory` 的 in-memory discard/cleanup helper
    那么 调用 MUST fail-fast(例如抛出 `RuntimeError`),而不是静默写入共享状态
  @req:r379 @human
  场景: refactor-does-not-introduce-unguarded-helper-writes
    - 必须成立：当 新增 artifacts helper API 或重构既有 helper；那么 任一会写 workflow-managed artifacts 的 helper MUST 包含相同的 owner-thread enforcement
    当 新增 artifacts helper API 或重构既有 helper
    那么 任一会写 workflow-managed artifacts 的 helper MUST 包含相同的 owner-thread enforcement
  @req:r385 @human
  场景: concurrent-workflows-publish-to-the-same-root-without-mutual
    - 必须成立：假如 两个独立 workflow 进程并发写入同一输出 root（`./out`）；当 两个 workflow 都成功完成 publish；那么 `./out/versions/<wf_exec_id_1>/` 与 `./out/versions/<wf_exec_id_2>/` MUST 同时存在
    假如 两个独立 workflow 进程并发写入同一输出 root（`./out`）
    当 两个 workflow 都成功完成 publish
    那么 `./out/versions/<wf_exec_id_1>/` 与 `./out/versions/<wf_exec_id_2>/` MUST 同时存在

  @req:r389 @human
  场景: field-id-alignment-preserves-data-under-duplicate-display-headers
    - 必须成立：假如 workflow 输出声明 header_fields_output_by=name 且多个字段共用相同展示名(例如多个指标块共用「人数」「金额」)；当 workflow write 节点消费 workflow-managed 中间工件并导出 xlsx/csv；那么 导出的每条数据行 MUST 按 field_id 位置正确取值,后续同名列 MUST NOT 被首列值填充;表头行 MUST 输出可重复的展示名
    假如 workflow 输出声明 header_fields_output_by=name 且多个字段共用相同展示名(例如多个指标块共用「人数」「金额」)
    当 workflow write 节点消费 workflow-managed 中间工件并导出 xlsx/csv
    那么 导出的每条数据行 MUST 按 field_id 位置正确取值,后续同名列 MUST NOT 被首列值填充;表头行 MUST 输出可重复的展示名

  @req:r389 @human
  场景: export-header-decoupled-from-alignment-key
    - 必须成立：假如 workflow-managed 中间工件的 header 为唯一 field_id 且 export_header 携带可重复展示名；当 写入节点执行字段对齐并写出表头行；那么 列对齐映射 MUST 基于 field_id 不得坍缩;表头行 MUST 使用 export_header 而非 field_id
    假如 workflow-managed 中间工件的 header 为唯一 field_id 且 export_header 携带可重复展示名
    当 写入节点执行字段对齐并写出表头行
    那么 列对齐映射 MUST 基于 field_id 不得坍缩;表头行 MUST 使用 export_header 而非 field_id

  @req:r393 @human
  场景: xlsx-rows-preserve-naive-datetime
    - 必须成立：假如 workflow-managed xlsx output contains naive datetime create_datetime；当 run completes and workbook is committed；那么 Excel cell MUST be a date/datetime value (not a stringified text cell due to InMemoryRows str fallback)
    假如 workflow-managed xlsx output contains naive datetime create_datetime
    当 run completes and workbook is committed
    那么 Excel cell MUST be a date/datetime value (not a stringified text cell due to InMemoryRows str fallback)

  @req:r393 @human
  场景: xlsx-rows-aware-datetime-fails-like-openpyxl
    - 必须成立：假如 workflow-managed xlsx output contains timezone-aware datetime；当 write/commit path runs；那么 system MUST NOT stringify; failure MUST be consistent with openpyxl timezone TypeError
    假如 workflow-managed xlsx output contains timezone-aware datetime
    当 write/commit path runs
    那么 system MUST NOT stringify; failure MUST be consistent with openpyxl timezone TypeError

  @req:r393 @human
  场景: xlsx-rows-bus-accepts-np-datetime64
    - 必须成立：假如 workflow-managed path materializes InMemoryRows containing np.datetime64；当 ROWS capture completes；那么 ROWS MUST retain np.datetime64; any failure MUST occur at Excel sink/precheck rather than ROWS gate
    假如 workflow-managed path materializes InMemoryRows containing np.datetime64
    当 ROWS capture completes
    那么 ROWS MUST retain np.datetime64; any failure MUST occur at Excel sink/precheck rather than ROWS gate

  @req:r24 @human
  场景: rows-plan-skips-eager-csv-copy
    - 必须成立：假如 a ROWS `ManagedArtifactPlan` holds 100k rows × 9 cols；当 `_collect_managed_artifact_outputs` runs；那么 no CSV copy MUST be created for that plan; only the rows artifact is published
    假如 a ROWS `ManagedArtifactPlan` holds 100k rows × 9 cols
    当 `_collect_managed_artifact_outputs` runs
    那么 no CSV copy MUST be created for that plan; only the rows artifact is published

  @req:r24 @human
  场景: csv-plan-still-emits-csv
    - 必须成立：假如 a CSV `ManagedArtifactPlan` targets a csv/file output；当 `_collect_managed_artifact_outputs` runs；那么 the CSV artifact MUST still be produced as before
    假如 a CSV `ManagedArtifactPlan` targets a csv/file output
    当 `_collect_managed_artifact_outputs` runs
    那么 the CSV artifact MUST still be produced as before

  @req:r25 @human
  场景: workbook-apply-materializes-typed-rows
    - 必须成立：假如 `apply_workbook_sheet` receives `InMemoryRows` with int/float/bool/None；当 apply completes；那么 the workbook sheet segment MUST own materialized `FieldValue` rows (not a live CSV reference SSOT)
    假如 `apply_workbook_sheet` receives `InMemoryRows` with int/float/bool/None
    当 apply completes
    那么 the workbook sheet segment MUST own materialized `FieldValue` rows (not a live CSV reference SSOT)

  @req:r25 @human
  场景: workbook-commit-writes-owned-typed-rows
    - 必须成立：假如 a workbook plan has materialized typed segments；当 commit writes openpyxl；那么 `ws.append` MUST receive the owned typed values after `escape_excel_formula` on strings only
    假如 a workbook plan has materialized typed segments
    当 commit writes openpyxl
    那么 `ws.append` MUST receive the owned typed values after `escape_excel_formula` on strings only

  @req:r25 @human
  场景: workbook-still-accepts-incsv-adapter
    - 必须成立：假如 `apply_workbook_sheet` receives `InMemoryCsv`；当 apply+commit succeed；那么 behavior MUST remain valid; cell values MAY be strings because the adapter input was CSV-equivalent
    假如 `apply_workbook_sheet` receives `InMemoryCsv`
    当 apply+commit succeed
    那么 behavior MUST remain valid; cell values MAY be strings because the adapter input was CSV-equivalent

  @req:r26 @human
  场景: release-after-final-write-consumer
    - 必须成立：假如 某 managed ROWS artifact 仅被一个 write node 消费且无下游 book_sheet_rows 依赖；当 该 write node 成功 apply 到 book plan；那么 系统 MUST 释放该 demand 侧内存 artifact
    假如 某 managed ROWS artifact 仅被一个 write node 消费且无下游 book_sheet_rows 依赖
    当 该 write node 成功 apply 到 book plan
    那么 系统 MUST 释放该 demand 侧内存 artifact

  @req:r26 @human
  场景: release-after-commit-or-discard
    - 必须成立：假如 workflow 结束并完成 commit_all 或 discard_all；当 资源生命周期收尾完成；那么 系统 MUST 释放 plan segment 行数据占用或丢弃 plan
    假如 workflow 结束并完成 commit_all 或 discard_all
    当 资源生命周期收尾完成
    那么 系统 MUST 释放 plan segment 行数据占用或丢弃 plan

  @req:r26 @human
  场景: book-sheet-rows-visibility-preserved
    - 必须成立：假如 下游 node 仍依赖 book_sheet_rows 读取某 producer 写入的 sheet；当 上游 write 已 apply 但下游尚未读取；那么 系统 MUST NOT 因过早释放 plan 导致可见性破坏
    假如 下游 node 仍依赖 book_sheet_rows 读取某 producer 写入的 sheet
    当 上游 write 已 apply 但下游尚未读取
    那么 系统 MUST NOT 因过早释放 plan 导致可见性破坏

  @req:r27 @human
  场景: yaml-residual-budget-fail-fast
    - 必须成立：假如 YAML resources.books 下残留 budget 字段；当 用户执行 validate 或解析；那么 系统 MUST fail-fast 并提示删除该字段（不得再指向 BookBudgetPolicy）
    假如 YAML resources.books 下残留 budget 字段
    当 用户执行 validate 或解析
    那么 系统 MUST fail-fast 并提示删除该字段（不得再指向 BookBudgetPolicy）

  @req:r27 @human
  场景: no-python-book-budget-api
    - 必须成立：当 调用方尝试构造或传入 BookBudgetPolicy / BookResourcePolicy(budget=...)；那么 该 API MUST 不可用（类型/参数不存在）
    当 调用方尝试构造或传入 BookBudgetPolicy / BookResourcePolicy(budget=...)
    那么 该 API MUST 不可用（类型/参数不存在）

  @req:r27 @human
  场景: pathless-writes-without-cell-sheet-budget
    - 必须成立：假如 pathless book 未配置任何 cell/sheet 预算；当 workflow 写入多 sheet / 多 cell；那么 系统 MUST NOT 因已移除的 max_sheets/max_total_cells 护栏 fail-fast
    假如 pathless book 未配置任何 cell/sheet 预算
    当 workflow 写入多 sheet / 多 cell
    那么 系统 MUST NOT 因已移除的 max_sheets/max_total_cells 护栏 fail-fast
