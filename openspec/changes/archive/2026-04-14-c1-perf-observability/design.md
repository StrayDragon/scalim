## Context

当前 `scalim` 的可观测性输出主要来自两类通道：

1) **stdlib logging 文本行**  
`performance/relations/pipeline/...` 等 subsystem 会把指标/进度拼成字符串（历史上以 `k=v` 为主），写入 `logging.getLogger("scalim.*")`。

2) **真实生产日志往往是“混合输出”**  
同一个 `.log` 文件里经常同时包含：
- 脚本 stdout（例如多行 SQL dump、print）
- warnings / traceback
- `scalim.*` 的 logging 行

这导致两个痛点：

- **机器解析困难**：`k=v`/自由文本对齐/新增字段等都容易造成下游解析器脆弱；不同 subsystem 的字段一致性难以长期治理。
- **人类/LLM 阅读浪费**：混合输出噪声大，用户很难快速抓住关键指标；LLM agent token 消耗极高。

因此本 change 的核心是：把 `scalim.*` 的 logging 升级为 **JSONL 结构化日志**，再由 `scalim-cli` 负责从“原始混合日志”中容错提取 JSON，并按场景渲染为 human-friendly / llm-friendly。

## Goals / Non-Goals

**Goals**

- `src/scalim/`（Python 3.6 运行时）提供 dependency-free 的 JSONL 结构化日志输出机制，覆盖 **所有 `scalim.*` logger**。
- 支持 **single-write**：启用 JSONL 后不再输出旧的 `k=v` 文本形态，避免双栈维护与 drift。
- 提供统一的结构化字段模型：核心字段稳定、可 join 的上下文自动注入（run/workflow/demand 归因），并支持 `compact/verbose` 两种 key profile（缩写/全称）。
- `scalim-cli`（Python 3.10+）新增 `log` 子命令：只解析 JSON（不猜 `k=v`），并对“多行 JSON/混合输出”做容错读取；输出 human-friendly/llm-friendly。
- `performance-observability` 等报告输出与结构化日志对齐：`performance/relations` 的 report 行以 `kind + fields` 的结构化记录输出，便于过滤/聚合。

**Non-Goals**

- 不做“从非结构化文本推断结构”的通用日志解析器（只解析 JSON）。
- 不引入 `schema_version` 等“强门禁版本字段”。我们处于快速迭代期，CLI 需要对输入做容错而不是把版本当 blocker。
- 不尝试把 JSONL 作为强稳定的外部 API（但会尽量保持关键字段语义稳定，并通过 CLI 做兼容渲染）。

## Decisions

### Decision 1: JSONL 记录结构采用 “固定顶层 + 分区子对象”，避免顶层膨胀

每条日志输出为单行 JSON object（JSONL），整体分为：

- **固定顶层（用于过滤/排序/快速 scan）**
  - `ts`：epoch 秒（float）
  - `lvl`：日志等级（int）
  - `lg`：logger name（string，如 `scalim.performance`）
  - `msg`：消息文本（string，作为保底可读字段）
  - `k`：kind（string，可选；用于“结构化事件分类”，例如 `performance.summary`、`relations.per_source`）

- **子对象（用于治理/扩展）**
  - `ctx`：上下文归因（run/workflow/demand 等）
  - `f`：本条记录的业务字段（metrics/参数/计数等）
  - `err`：异常信息（发生异常时）

说明：
- 不要求每条记录都有 `k/ctx/f/err`；但必须至少有 `ts/lvl/lg/msg`。
- `ctx/f` 的 key 会受 profile 影响（见 Decision 2）。

### Decision 2: 字段 key 同时支持全称与缩写，但 runtime 默认只输出一种 profile

维护一份“字段元信息”（data class / registry）作为 SSOT，要求：

- 每个字段定义：
  - `full`：全称 key（例如 `workflow_exec_id`）
  - `abbr`：缩写 key（例如 `wf`），全局唯一
- runtime 输出选择 `profile=compact|verbose`：
  - `compact`：输出缩写 key，减少体积与 token
  - `verbose`：输出全称 key，利于手动排障
- `scalim-cli` 需要同时支持两种输入：根据 key 集合自动识别并映射到统一内部模型。

这样既满足“长期可维护”（全称自解释、缩写唯一可治理），又满足“LLM token 节省”（compact profile）。

### Decision 3: 仍基于 stdlib `logging`，但只作用于 `scalim.*` 命名空间

约束：`src/scalim/` 必须 Python 3.6 兼容，且不依赖 structlog 等第三方库。

方案：

- 提供 `install_jsonl_logging(...)` 之类的显式 API，在 `scalim` root logger（`logging.getLogger("scalim")`）挂载 JSONL handler/formatter。
- handler 默认写入 stdout/stderr（由配置决定），并设置：
  - `propagate = False`（避免宿主再输出一份）
  - idempotent 安装（重复调用不产生重复 handler）
- 未启用时保持库行为：不 `basicConfig()`，不改 root logger，保持 `NullHandler` 策略。

### Decision 4: 上下文注入采用 thread-local “LogContext stack”，并在执行编排边界设置

目标：保证不同 subsystem 的日志可以在单行内 join（同一条记录无需重复传参）。

实现方向（语义）：

- 使用 `threading.local()` 保存当前上下文（可叠加/嵌套）。
- 在以下边界注入/恢复：
  - `run_ir(...)` standalone demand
  - workflow 执行的每个 node（已有 `event_meta_defaults`/workflow context，可复用）
- JSONL formatter 在序列化时自动读取当前 thread-local ctx 并附带到记录中。

上下文字段建议（按可得性出现）：
- `run_id`
- `workflow_exec_id` / `workflow_node_id` / `workflow_node_decl_order`
- `demand` / `demand_path`

### Decision 5: `performance/relations` 报告行从“拼字符串”迁移为“结构化 kind + fields”

原先的 `console_report.build_line()` + `format_kv()` 依赖字符串拼接与排序；升级后：

- 每一行 report 输出对应一条 JSONL record
- `k` 使用稳定 token（例如 `performance.summary`、`performance.stage`、`relations.summary`、`relations.per_source`）
- 指标字段放入 `f`（或 `fields`），归因字段放入 `ctx`
- 这也为后续 `scalim-cli` 做聚合/Top-N/折叠提供稳定输入。

### Decision 6: CLI 只解析 JSON，并提供“多行 JSON 自动拼接”的容错读取

`scalim-cli` 新增 `log` 子命令：

- 输入为文件或 stdin
- 读取策略：
  - 逐行扫描
  - 遇到疑似 JSON 起始后累积行，直到能 `json.loads()` 成功（解决 copy/paste 破坏单行的场景）
  - 无法解析则丢弃并继续（可选输出诊断）
- 输出模式：
  - human：分组/折叠/截断长字段/高亮错误
  - llm：在 token 预算内聚合、Top-N、去噪、生成可直接喂给 agent 的摘要

## Migration Plan

- 该 change 以“最终替换 `k=v`”为目标：启用 JSONL 后 single-write，不再维护旧输出形态。
- 分阶段推进（实现侧）：
  1. 先让 `scalim.*` 在启用 JSONL 时全量输出 JSON（即使某些行只有 `msg`，也必须是有效 JSON）
  2. 再逐步把关键 subsystem（`performance/relations/pipeline`）迁移为 `kind + fields + ctx` 的结构化输出
  3. CLI 同步落地：保证用户能拿到 human/llm 友好视图

## Risks / Trade-offs

- **Breaking**：下游如果依赖旧文本格式会被打断 → 用 `scalim-cli log` 作为官方迁移路径。
- **宿主 logging 干预**：宿主可能自行配置 handler/formatter → 我们只控制 `scalim.*`，并保持默认不主动安装（除非显式启用）。
- **性能开销**：JSON 序列化有成本 → 需要确保 formatter 实现轻量、且在未启用时不引入额外开销。

## Open Questions

- 环境变量命名与开关策略（例如 `SCALIM_LOG_FORMAT=jsonl` / `SCALIM_LOG_PROFILE=compact` / `SCALIM_LOG_STREAM=stderr` 等）如何定稿，是否与现有项目的 `SCALIM_DEBUG` 约定对齐？
- `ctx` 字段是否需要提供强约束的字段白名单（避免随意膨胀）？
- CLI 的 llm-friendly 输出是否需要提供一个“目标 token 预算”选项（例如 `--budget-chars`）？
