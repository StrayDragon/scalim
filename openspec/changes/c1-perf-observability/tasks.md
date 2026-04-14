## 0. Structured JSONL Logging (P0)

- [ ] 0.1 新增 delta spec：`specs/structured-logging/spec.md`（定义 JSONL 记录结构、上下文字段、compact/verbose profile 与 key 元信息治理约束；明确不引入 schema_version 门禁）
- [ ] 0.2 Runtime 实现 JSONL logging 安装入口（stdlib logging + handler/formatter，仅作用于 `scalim.*`；支持 stdout/stderr；`propagate=False`；重复安装幂等）
- [ ] 0.3 Runtime 增加 thread-local `LogContext`（支持嵌套/恢复），并在执行编排边界注入 ctx：
  - standalone demand：`run_id` + `demand`
  - workflow node：`workflow_exec_id/workflow_node_id/...` + `demand/demand_path`
- [ ] 0.4 将 `scalim.performance` / `scalim.relations` / `scalim.pipeline` 的“console report 行”迁移为 JSONL 结构化记录（`kind + ctx + fields`），停止输出旧 `k=v` 文本行
- [ ] 0.5 解决重复输出问题（确保 observer/report 的输出不会因多次 close 或多路径触发而重复；必要时调整 `RelationObserver.close()` 语义）
- [ ] 0.6 增加测试：断言启用 JSONL 时所有 `scalim.*` 输出均为可解析 JSON object（单行），且关键 ctx 字段可 join

## 1. scalim-cli 日志解析与渲染 (P0)

- [ ] 1.1 `scalim-cli` 新增 `log` 子命令族：`scalim-cli log fmt|summarize`（支持 file/stdin）
- [ ] 1.2 实现容错 JSON 读取（只解析 JSON，不猜 `k=v`）：
  - 忽略非 JSON 行
  - 支持“多行 JSON 自动拼接/修复”（copy/paste 或换行破坏）
  - 同时支持 compact/verbose key（通过字段元信息映射到统一内部模型）
- [ ] 1.3 实现 `human-friendly` 渲染：按 ctx 分组、折叠重复、截断长字段、突出 warnings/errors
- [ ] 1.4 实现 `llm-friendly` 渲染：聚合/Top-N/去噪 + token/字符预算控制，输出可直接喂给 agent 的摘要（可选 Markdown）
- [ ] 1.5 增加 CLI 测试覆盖：容错读取、多 profile 输入、输出稳定性

## 2. Demand Attribution (P1)

- [ ] 2.1 在 workflow 编排侧注入 demand 归因 meta：扩展 `src/scalim/workflow/execute_controller.py` 的 `event_meta_defaults`，追加 `demand`（`DemandIr.name`）与 `demand_path`
- [ ] 2.2 为 standalone demand 执行路径注入 `demand` 归因（在 `run_ir` 入口侧设置默认 ctx）
- [ ] 2.3 确保 `performance/relations` 输出的 JSONL 记录在 ctx 中携带 `demand/workflow_node_id/demand_path`（当存在时）
- [ ] 2.4 测试覆盖：workflow 与非 workflow 两种路径均可 grep-join

## 3. main_source streaming vs source lookup (P1)

- [ ] 3.1 在 `src/scalim/execution/pipeline/base/pipeline.py` 中实现 wants-gated 的 per-batch streaming wall-time 计时（“每批拉取 batch_rows 的时间”）
- [ ] 3.2 通过 `EVENT_STAGE_SPAN` 发出 `stage="stream"` 的 stage spans（按 batch_num 归因）
- [ ] 3.3 在 performance 的 JSONL 报告中新增 `kind=performance.loader_breakdown`：输出 `stream_s/source_lookup_s/compute_s/write_s/untracked_overhead_s`
- [ ] 3.4 单测：streaming 计时口径正确（不与 `loader/compute/write` 混淆）

## 4. Per-loader / Per-source Timing (P1)

- [ ] 4.1 拆分 `PerformanceConfig.include_details`：将 per-batch verbose 与 per-loader stats 解耦（例如 `include_batch_lines/include_loader_stats/include_loader_top_n`）
- [ ] 4.2 扩展 loader stats（分位数 + roundtrip 口径；必要时对 durations 做 hard cap）
- [ ] 4.3 performance JSONL 输出新增 `kind=performance.loader_top`（按 total_s 排序 top-N）与可选 `kind=performance.loader` 全量明细
- [ ] 4.4 单测：排序稳定、字段齐全、低噪声默认可用

## 5. Batch Duration Distribution (P2)

- [ ] 5.1 performance JSONL 输出新增 `kind=performance.batch_stats`：min/max/p50/p90/stddev
- [ ] 5.2 单测：batch_count>0 时输出且口径正确

## 6. Per-field Compute Profiling (opt-in, P2)

- [ ] 6.1 设计并实现 operator-level compute span 的 wants-gated 上报（每个 ComputeOperator 每批最多一条 span）
- [ ] 6.2 聚合并输出 `kind=performance.field_top`（top-N），默认关闭
- [ ] 6.3 测试：profiling 关闭无额外 span；开启后输出符合预期

## 7. Specs & QA

- [ ] 7.1 更新/补充 delta specs，使其覆盖已实现行为：
  - `specs/structured-logging/spec.md`
  - `specs/performance-observability/spec.md`（输出形态从 `k=v` 调整为 JSONL record 语义）
- [ ] 7.2 运行 `just openspec-check`（sanitize + OpenSpec validate）
- [ ] 7.3 运行 `just qa`（lint/tests + drift gates）
