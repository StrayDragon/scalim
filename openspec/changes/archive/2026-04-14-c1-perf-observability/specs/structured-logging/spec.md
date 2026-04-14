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

#### Scenario: every JSONL record has stable base fields
- **GIVEN** structured logging 已启用
- **WHEN** 任意 `scalim.*` logger 产生一条日志记录
- **THEN** 输出 JSON object MUST 至少包含 `timestamp/level/logger/message`（或 compact profile 的对应缩写）

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

#### Scenario: CLI can normalize compact keys to full keys
- **GIVEN** 输入日志为 compact profile（使用缩写 key）
- **WHEN** `scalim-cli log ...` 解析并标准化 key
- **THEN** 解析结果 MUST 可映射到全称 key 的统一内部模型（例如 `run_id` 而非 `rid`）

### Requirement: structured logging MUST NOT require schema_version as a parsing gate

系统 MUST NOT 要求每条记录包含 `schema_version`（或等价强门禁字段）才能被解析。

说明：我们处于快速迭代期，CLI 的策略应以“容错解析 + 渐进兼容”为主，而不是把版本字段当 blocker。

#### Scenario: records without schema_version are still valid inputs
- **GIVEN** 一条结构化日志记录不包含 `schema_version`
- **WHEN** `scalim-cli` 解析该记录
- **THEN** 该记录 MUST 被视为有效输入并可被渲染/聚合

### Requirement: joinable attribution context MUST be injected automatically when available

系统 MUST 支持自动注入可 join 的归因上下文（在可获取时）：

- `run_id`（或等价内部稳定运行标识）
- workflow 场景：`workflow_exec_id`、`workflow_node_id`、（可选）`workflow_node_decl_order`
- demand 归因：`demand`、（可选）`demand_path`

并满足：
- 该注入 MUST 不要求每次 `logger.info(...)` 调用手动传入（应由运行时上下文机制自动附带）
- 不同 subsystem（例如 `performance/relations/pipeline`）输出 MUST 能通过这些字段 join

#### Scenario: context is injected without passing extra fields to logger calls
- **GIVEN** runtime 在执行边界设置了当前 run/workflow/demand 上下文
- **WHEN** 任意 subsystem（例如 `performance`）输出一条结构化记录
- **THEN** 该记录 MUST 自动携带可 join 的 `run_id/workflow_node_id/demand` 等上下文（当这些字段可获取时）

### Requirement: enabling structured logging MUST be configurable via env and explicit Python API

系统 MUST 提供多种启用方式（至少包含）：

- 环境变量开关（适合脚本/批处理/容器环境）
- 显式 Python API（适合集成到服务或上层框架）

系统 SHOULD 支持额外配置项（例如输出 stream、level、profile）。

#### Scenario: structured logging can be enabled via env and via explicit API
- **GIVEN** 用户通过环境变量启用 structured logging
- **WHEN** 运行一次 demand/workflow 执行
- **THEN** `scalim.*` 的输出 MUST 为 JSONL
- **AND** 当用户改为调用显式 Python API 启用 structured logging 时，输出 MUST 同样为 JSONL

### Requirement: the system MUST be single-write when structured logging is enabled (no legacy kv output)

当启用 structured-logging 时，系统 MUST 保持 single-write：

- 系统 MUST 不再输出旧的 `k=v`/自由文本“console report 行”（避免双栈维护与重复输出）
- `scalim-cli` 成为官方的“人类可读/LLM 友好”渲染入口

#### Scenario: legacy kv console report lines are not emitted when JSONL is enabled
- **GIVEN** structured logging 已启用
- **WHEN** pipeline 运行并触发 performance/relations 的 report 输出
- **THEN** 输出 MUST 只包含 JSONL records（single-write）
- **AND** 输出 MUST NOT 包含旧的 `k=v` console report 文本行

### Requirement: `scalim-cli` SHALL provide human-friendly and llm-friendly renderers for structured logs

`scalim-cli` SHALL 提供结构化日志渲染能力：

- human-friendly：分组/折叠/截断长字段/突出告警与错误
- llm-friendly：在预算内做聚合/Top-N/去噪，输出可直接喂给 agent 的摘要

并且 MUST 支持对“原始混合日志”的容错读取：

- 忽略非 JSON 行
- 支持多行 JSON 自动拼接（直到可解析）

#### Scenario: CLI can format and summarize structured logs from a mixed file
- **GIVEN** 输入为一份混合日志文件（JSONL records + 非 JSON 行）
- **WHEN** 用户运行 `scalim-cli log fmt <file>` 与 `scalim-cli log summarize <file> --budget-chars=<n>`
- **THEN** CLI MUST 忽略非 JSON 行并输出 human-friendly 格式
- **AND** summarize 输出 MUST 在预算内生成 llm-friendly 摘要
