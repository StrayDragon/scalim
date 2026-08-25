# language: zh-CN
# capability: tools-console-reports
# purpose: 定义 console 报告输出契约：仅依赖标准库 `logging` 的逐行 `k=v` 文本输出，无表格/边框依赖，per-entity 明细以重复行表达，样本有界。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: tools-console-reports

  @req:r80 @human
  场景: console reports MUST be dependency-free and line-oriented
    - 系统 MUST 将 `console` 报告（或等价的 “打印/展示到日志” 输出）实现为仅依赖 Python 标准库 `logging` 的逐行（line-oriented）文本输出。 系统 MUST NOT 依赖 `scalim.vendor.literich`（或任何表格/面板渲染器）来完成 console 报告展示。

  @req:r324 @human
  场景: console report lines MUST use stable prefix + kind token + k=v fields
    - 系统 MUST 使用稳定前缀 `[scalim] <subsystem>:` 输出 console 报告行，并在每行前缀后使用稳定 kind token 表示该行语义（例如 `summary`、`per_source`、`loader` 等）。 系统 MUST 以稳定 `k=v` 形式表达诊断字段，且 key 顺序 MUST 稳定（字典序），值为 `None` 的字段 MUST 被省略。

  @req:r447 @human
  场景: console report MUST NOT rely on alignment or box drawing
    - 系统 MUST 将 console 报告视为可被 grep/日志采集处理的文本流，不得将“列对齐/固定宽度”作为信息载体。 实现 MUST NOT 以 “表格边框/对齐空格/等宽假设” 表达语义（例如不得要求用户通过 `│`/`┌─┐` 等 box drawing 或 padding 才能理解字段归属）。

  @req:r536 @human
  场景: per-entity breakdown MUST be emitted as repeated lines
    - 当报告包含 “按实体拆分”的明细（例如 `per_source` / `per_loader` / `per_stage`），系统 MUST 以重复的逐行输出表达该明细，而不是把其嵌入为对齐表格。

  @req:r610 @human
  场景: multi-line details MUST be bounded and individually line-oriented
    - 当报告需要输出样本/详情（例如 type mismatch samples），系统 MUST： - 输出一行 “summary line” 指明 `showing=N`（或等价字段） - 随后将每条样本作为独立的一行输出（每行仍遵循 prefix/kind/`k=v` 的约定，或以固定缩进并保持 `k=v`） - 样本数量 MUST 有界（例如仅输出前 N 条）
  @req:r80 @human
  场景: console-report-does-not-require-rendering-dependencies
    - 必须成立：假如 环境未安装 `rich` 等可选依赖；当 用户启用 observability 并选择 `report_format=console`；那么 console 输出 MUST 正常产生
    假如 环境未安装 `rich` 等可选依赖
    当 用户启用 observability 并选择 `report_format=console`
    那么 console 输出 MUST 正常产生
  @req:r324 @human
  场景: stable-prefix-and-stable-k-v-ordering
    - 必须成立：当 系统输出一行 console 报告并包含字段 `{b: 2, a: 1, skip: None}`；那么 该行 MUST 以 `[scalim] <subsystem>:` 开头
    当 系统输出一行 console 报告并包含字段 `{b: 2, a: 1, skip: None}`
    那么 该行 MUST 以 `[scalim] <subsystem>:` 开头
  @req:r447 @human
  场景: report-remains-readable-without-monospace-rendering
    - 必须成立：当 读者在比例字体/日志系统 UI 中查看 console 输出；那么 输出中的关键语义 MUST 仍可通过 kind token 与 `k=v` 直接读出
    当 读者在比例字体/日志系统 UI 中查看 console 输出
    那么 输出中的关键语义 MUST 仍可通过 kind token 与 `k=v` 直接读出
  @req:r536 @human
  场景: per-source-is-emitted-as-multiple-lines
    - 必须成立：假如 关联命中统计包含多个 `source_id`；当 系统输出 console 报告；那么 系统 MUST 为每个 `source_id` 输出一行 kind=`per_source` 的记录
    假如 关联命中统计包含多个 `source_id`
    当 系统输出 console 报告
    那么 系统 MUST 为每个 `source_id` 输出一行 kind=`per_source` 的记录
  @req:r610 @human
  场景: samples-output-is-bounded-and-line-oriented
    - 必须成立：假如 系统收集到 100 条 type mismatch 样本；当 系统输出 console 报告；那么 系统 MUST 明确输出 `showing=<N>`（N 为有界数，例如 5）
    假如 系统收集到 100 条 type mismatch 样本
    当 系统输出 console 报告
    那么 系统 MUST 明确输出 `showing=<N>`（N 为有界数，例如 5）
