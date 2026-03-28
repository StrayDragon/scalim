## Context

代码质量与可维护性问题往往不是“某个 bug”，而是“缺少边界 + 缺少 guardrail”的系统性结果。当前 repo 的 SSOT/门禁体系已经较丰富（OpenSpec、docs governance、drift checks、marimo suites），但在以下方面仍存在可治理空间：
- 热点模块体量过大，职责边界不清晰；
- 错误/日志输出策略在多个入口分叉；
- 生成物门禁清单分散在 `justfile`，扩展时容易漏；
- 某些“新增时需要显式决策”的点（事件 dispatch map、内部 utils）缺少 fail-fast。

## Goals / Non-Goals

**Goals:**
- 把维护性提升为可执行的 SSOT：清单化、脚本化、可回归。
- 用小步重构降低风险：拆分模块时保持行为等价（输出/事件/错误语义不变）。
- 统一错误/日志对外表现：既可诊断又不泄露。

**Non-Goals:**
- 不追求一次性“全库大重构”；按热点与收益分期推进。
- 不在此 change 内引入新的格式化/构建工具链（遵循现有 ruff/just 体系）。

## Decisions

### 1) 巨型文件拆分：按领域 + 阶段分包

决策：
- 对 >1k 行热点模块进行拆分，优先按“阶段”切割（parse/validate/plan/execute/report），其次按“领域对象”切割（workflow resources、output composition、IR 等）。
- 拆分后引入更窄的公开接口（内部模块之间通过显式数据结构/ABC 契约连接），避免循环依赖。

### 2) 错误类型与对外消息：集中化

决策：
- 同名异常类型只保留一个定义（例如 workflow config error），其余入口只做包装补充上下文（source_path/loc/path）。
- 引入单点“异常→对外消息”格式化工具（默认 redacted；显式 debug 才 full），并在 CLI JSON、viz bundle、workflow report 等出口统一使用。

### 3) 日志策略：用户日志 vs 调试日志分离

决策：
- 用户可见的结构化日志统一走 `loggingx`（prefix + kv）；runtime 禁止混用 `print`。
- TTY 美观输出只存在于明确的“pretty observer/CLI 命令”，且与结构化 logger 输出互斥。

### 4) 生成物门禁清单 SSOT 化

决策：
- 新增 `generated-artifacts-manifest`（机器可读），列出所有生成物与其生成入口（`just gen-*`/脚本）。
- `justfile` 的 drift checks 不再硬编码路径列表，而是调用单一脚本读取 manifest 并执行校验。

### 5) Guardrails：新增必须显式决策

决策：
- 为事件 dispatch map 提供完整性校验：新增核心事件时必须显式加入 dispatch 或明确忽略（fail-fast）。
- 为 `_internal/utils` 写极短治理说明（允许进入的内容类型/依赖方向），防止变成杂物间。
- 为“模块体量阈值”提供轻量护栏（仅对热点模块与阈值触发时 fail-fast）。

## Risks / Trade-offs

- [重构回归] 拆分模块可能引入微妙行为变化：→ 以现有回归（examples/spec checks）+ 新增行为等价测试护栏兜底。
- [门禁噪音] 新增 guardrail 可能短期红：→ 分期引入，先以 warn-report 模式观察，再提升为 fail-fast。
- [维护成本] manifest/脚本本身需要维护：→ 把“维护 manifest”纳入变更流程（新增生成物必须显式登记）。

## Migration Plan

- 阶段 1：引入 manifest + 脚本化 drift checks；先不拆代码，先把门禁 SSOT 化。
- 阶段 2：收敛异常/日志策略（低风险、收益高）。
- 阶段 3：对热点模块做拆分（每次拆分一个模块，并配套行为等价回归）。

## Open Questions

- 模块体量阈值用“行数”还是“复杂度指标”（cyclomatic）更合适？（先用行数作为粗 guardrail。）
- 对外错误 redaction 的 debug 开关应放在 CLI flag、环境变量还是 runtime options？

