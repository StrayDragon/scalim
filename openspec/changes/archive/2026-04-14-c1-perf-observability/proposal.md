## Why

在真实生产环境里，我们经常需要从日志中快速判断：
- 哪个 demand / workflow 节点最慢？
- 主要耗时在 streaming 还是 lookup 还是 compute？
- 哪个 source/loader 最慢？是否存在明显倾斜？

但目前 `scalim.*` 的日志很难“稳定地被机器解析 + 方便人类阅读”，主要问题来自两点：

1. **输出形态偏文本**：大量信息通过 `k=v`/自由文本拼接写入 `logging`，下游想聚合/过滤/渲染只能写脆弱的解析器。
2. **真实日志常常是混合输出**：stdout（脚本/SQL dump/print）、warnings、traceback、以及 `logging` 混在一个文件里，导致单纯 grep 很痛苦，LLM agent 读起来也极其浪费 token。

因此我们希望把 `scalim.*` 的可观测性输出升级为 **JSONL 结构化日志**，并提供一个独立的 `scalim-cli` 工具链，让用户可以从“原始混合日志”中容错提取 JSON 记录，再按需要渲染为：
- 人类可读（human-friendly）
- LLM token 友好（llm-friendly）

## What Changes

本变更包含两部分（runtime + CLI），并以“最终替换 `k=v` 输出”为目标：

### 1) Runtime：`scalim.*` 统一 JSONL 结构化日志（Python 3.6 兼容，无第三方依赖）

- 在 `src/scalim/` 内基于 stdlib `logging` 提供 JSONL 输出机制：每条日志是一行 JSON object（line-oriented）。
- **单写（single-write）**：启用 JSONL 后不再输出旧的 `k=v` 文本行，避免双栈维护。
- 提供字段元信息（全称 + 唯一缩写）以支持两种 profile：
  - `compact`：更省体积与 token
  - `verbose`：更自解释（便于排障/手看原始日志）
- 支持“上下文自动注入”（例如 `run_id`、`workflow_exec_id`、`workflow_node_id`、`demand`、`demand_path` 等），保证不同 subsystem（`performance`/`relations`/`pipeline`/其它 `scalim.*` logger）输出可 join。
- 提供多种配置方式（不强依赖 YAML authoring）：
  - 环境变量（适合脚本/批处理）
  - 显式 Python API（适合服务/库集成）
  - `RunOptions`/执行入口（适合 YAML DSL runtime）

### 2) CLI：`scalim-cli` 增强日志解析与渲染（Python 3.10+ 可用第三方库）

- 新增 `scalim-cli log ...` 子命令，输入可以是：
  - 纯 JSONL 文件
  - 混合日志文件（其它 stdout/warnings 夹杂）
  - copy/paste 的片段（可能把单条 JSON 打断成多行）
- CLI 只解析 JSON（不去猜 `k=v`），并提供容错读取：
  - 忽略非 JSON 行
  - 自动拼接/修复“多行 JSON”直到可解析
- 输出转换：
  - `human-friendly`：按上下文分组、折叠重复行、突出关键指标
  - `llm-friendly`：在 token 预算内做聚合/Top-N/去噪，便于直接喂给 agent

## Capabilities

### New Capabilities
- `structured-logging`: `scalim.*` JSONL 结构化日志输出 + key profile（compact/verbose）+ 上下文注入 + CLI 渲染

### Modified Capabilities
- `performance-observability`: 保持原有 perf/relations 指标口径，输出形态切换为 JSONL，并与结构化日志上下文对齐（便于跨 subsystem join/聚合）。

## Impact

- **Breaking change**：`scalim.*` 的默认可观测性输出形态将从 `k=v` 文本迁移到 JSONL（启用后 single-write）。任何依赖旧文本解析的下游需要迁移到 `scalim-cli log` 或改为解析 JSON。
- **维护成本下降**：从“拼字符串 + 人肉保证字段一致”升级为“结构化字段 + 统一序列化”，减少长期 drift。
- **用户体验提升**：同一份原始 log 文件可通过 CLI 选择性渲染，既适合人读，也适合 LLM 处理。
