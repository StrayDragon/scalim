# structured-logging (delta) Specification

## ADDED Requirements

### Requirement: when enabled, `scalim.*` logs MUST be emitted as JSONL (one JSON object per line)

当启用结构化日志时，系统 MUST 将所有 `scalim.*` logger 的可见输出统一为 JSONL：

- 每条日志 MUST 是 **单行** JSON object（JSON Lines）
- MUST 可写入 `stdout/stderr`（由配置决定）
- MUST 保持 line-oriented（便于 `tail -f`/流式处理/管道）

说明：该 requirement 约束的是“启用 structured-logging 时”的输出形态；未启用时系统仍可保持库默认行为（不主动配置 root logging）。

#### Scenario: mixed raw log can be parsed by scanning JSON objects
- **GIVEN** 一个混合日志文件（包含 stdout 文本、warnings、以及结构化日志 JSON）
- **WHEN** `scalim-cli` 逐行扫描并仅解析 JSON object
- **THEN** 结构化日志记录 MUST 可被稳定提取（不依赖 `k=v` 或正则猜测）

### Requirement: JSONL record MUST include a minimal stable base set of fields

每条 JSONL record MUST 至少包含以下“基础字段”（字段名可能因 profile 不同而不同，见后续 requirement）：

- `timestamp`（或缩写）：事件时间（epoch seconds）
- `level`（或缩写）：日志等级（等价于 stdlib logging level）
- `logger`（或缩写）：logger name（例如 `scalim.performance`）
- `message`（或缩写）：消息文本（作为兜底可读字段）

系统 MAY 追加：
- `kind`（用于结构化分类/渲染）
- `context`（上下文归因）
- `fields`（业务字段/指标）
- `error`（异常信息）

### Requirement: the system MUST provide key metadata with full name + unique abbreviation, and support compact/verbose profiles

系统 MUST 维护一份字段元信息（SSOT），用于保证 key 的可治理性与可演进性：

- 每个字段 MUST 同时定义：
  - 全称 key（full）
  - 唯一缩写 key（abbr，必须全局唯一）
- 系统 MUST 支持至少两种输出 profile：
  - `compact`：输出缩写 key（更省体积/token）
  - `verbose`：输出全称 key（更自解释）
- 在一次运行中，系统 SHOULD 只选择一种 profile 输出（避免同一文件里混用导致难维护）
- `scalim-cli` MUST 能同时解析两种 profile 的输入，并映射到统一内部模型

### Requirement: structured logging MUST NOT require schema_version as a parsing gate

系统 MUST NOT 要求每条记录包含 `schema_version`（或等价强门禁字段）才能被解析。

说明：我们处于快速迭代期，CLI 的策略应以“容错解析 + 渐进兼容”为主，而不是把版本字段当 blocker。

### Requirement: joinable attribution context MUST be injected automatically when available

系统 MUST 支持自动注入可 join 的归因上下文（在可获取时）：

- `run_id`（或等价内部稳定运行标识）
- workflow 场景：`workflow_exec_id`、`workflow_node_id`、（可选）`workflow_node_decl_order`
- demand 归因：`demand`、（可选）`demand_path`

并满足：
- 该注入 MUST 不要求每次 `logger.info(...)` 调用手动传入（应由运行时上下文机制自动附带）
- 不同 subsystem（例如 `performance/relations/pipeline`）输出 MUST 能通过这些字段 join

### Requirement: enabling structured logging MUST be configurable via env and explicit Python API

系统 MUST 提供多种启用方式（至少包含）：

- 环境变量开关（适合脚本/批处理/容器环境）
- 显式 Python API（适合集成到服务或上层框架）

系统 SHOULD 支持额外配置项（例如输出 stream、level、profile）。

### Requirement: when structured logging is enabled, the system MUST be single-write (no legacy `k=v` output)

当启用 structured-logging 时：

- 系统 MUST 不再输出旧的 `k=v`/自由文本“console report 行”（避免双栈维护与重复输出）
- `scalim-cli` 成为官方的“人类可读/LLM 友好”渲染入口

### Requirement: `scalim-cli` SHALL provide human-friendly and llm-friendly renderers for structured logs

`scalim-cli` SHALL 提供结构化日志渲染能力：

- human-friendly：分组/折叠/截断长字段/突出告警与错误
- llm-friendly：在预算内做聚合/Top-N/去噪，输出可直接喂给 agent 的摘要

并且 MUST 支持对“原始混合日志”的容错读取：

- 忽略非 JSON 行
- 支持多行 JSON 自动拼接（直到可解析）
