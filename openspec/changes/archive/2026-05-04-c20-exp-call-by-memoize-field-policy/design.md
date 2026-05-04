## Context

本变更面向 `ctx-free call_by` 的执行期 LRU 记忆化（memoization）实验能力，补齐“字段选择策略”这一关键治理点。

在真实报表场景中，`call_by` 派生字段常呈现两极分化：

- **低基数/高重复**：同一字段在大量行上反复以相同依赖元组调用，适合缓存；可显著降低 Python 调用与业务函数开销。
- **高基数/低重复**：依赖元组几乎每行都不同，缓存命中率低，反而增加内存与额外哈希/字典操作成本。

因此，仅靠“框架自动判断”很难覆盖全部业务形态；我们需要提供一个**严格、稳定、可线上验证**的配置面，让用户可以在不改业务代码的前提下决定哪些字段参与缓存、哪些字段明确不参与，并辅以可选的 `scalim.performance` 聚合日志用于 ROI 判断。

约束：

- `src/scalim/**` 运行时必须兼容 Python 3.6。
- 不引入任何第三方依赖（用户环境可能严格限制安装/审核）。
- 能力先以实验性环境变量提供：统一使用 `SCALIM_EXP_` 前缀；默认关闭。
- 不能泄露业务数据：日志仅输出计数/比率/字段名等元信息，不输出依赖值本身。

## Goals / Non-Goals

**Goals:**

- 提供字段级 allow/deny 过滤策略，使用户可控地启用 `ctx-free call_by` LRU 缓存。
- 提供可选的 `scalim.performance` 聚合日志（hit/miss/unique/evict/disabled），便于线上仅靠日志判断投入产出比。
- 默认关闭；即使开启也必须有硬内存上限（按字段 LRU 容量控制），并具备“高基数字段快速降级”的保护策略（例如字段级禁用）。

**Non-Goals:**

- 不引入新的 DSL 语法，不在 YAML 中新增字段来表达缓存策略（实验阶段先用 env）。
- 不改变 `call_by`/`compute` 的语义与错误类型（缓存仅缓存“成功结果”，异常不缓存）。
- 不在本变更中引入跨字段 fusion / batch call 等更大粒度变更（另行规划）。

## Decisions

### 1) 以环境变量提供实验性配置（`SCALIM_EXP_` 前缀），默认关闭

决策：以 env 作为唯一配置面，避免侵入用户业务配置；命名使用实验前缀以便后续治理与迁移。

拟定 env：

- `SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES=<int>`
  - `<=0` 或未设置：完全关闭 memoization
  - `>0`：对满足条件的字段启用“按字段 LRU”，容量为该值
- `SCALIM_EXP_CALL_BY_MEMOIZE_ALLOW=<csv patterns>`（可选）
- `SCALIM_EXP_CALL_BY_MEMOIZE_DENY=<csv patterns>`（可选）
- `SCALIM_EXP_CALL_BY_MEMOIZE_LOG_STATS=<bool/int>`（可选；单独控制）

工程治理：

- `src/scalim/_project_constants.py` 为生成物；环境变量名应在 `pyproject.toml` 内声明并由 `just gen-project-constants` 生成常量，避免手写漂移。
- 当前生成器仅覆盖 `tool.scalim.env.*` 的既有子节；实现时需要扩展为包含实验项（例如新增 `tool.scalim.env.experiments`，或扩展现有 probes 节点并保持语义清晰）。

### 2) 字段过滤策略：allow/deny + 通配符匹配，deny 优先

决策：提供两组 patterns：

- **allow**：当 allow 非空时，仅允许匹配任一 allow pattern 的字段参与缓存；allow 为空表示“默认全量候选”。
- **deny**：匹配任一 deny pattern 的字段强制不参与缓存（即使 allow 命中也排除）；deny 具有更高优先级。

pattern 语义：

- 采用稳定的“shell 风格通配符”匹配（`*`、`?`、字符类 `[]`），并以“字段 key（`field_id`）的原始字符串”作为匹配对象。
- 解析为逗号分隔（CSV-ish）：按 `,` 分割、`strip()`、忽略空项；不支持转义（足够简单且可预期）。

### 3) 缓存语义边界：仅 `ctx-free call_by` + 缓存 transform 前结果

决策：

- 仅对 `ctx-free call_by` 生效（即调用不需要 `ctx` 注入的字段）；对 `$ctx` 相关字段不启用缓存，避免把“隐式上下文依赖”变成缓存 key 的一部分并引入语义争议。
- 缓存值为 **value_transform 前** 的 calculator 返回值：减少“transform 可能依赖 ctx 或外部状态”的语义风险（即使目前大多为纯函数）。
- 仅缓存“成功返回值”；异常路径不缓存，保持错误触发频率与时机尽可能接近原语义。

### 4) 保护策略：内存上限 + 字段级快速降级

决策：

- LRU 容量以 `SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES` 作为硬上限，避免无界增长。
- 对高基数字段，需要支持“字段级禁用（disabled）”：
  - 触发条件建议基于运行中统计（例如达到容量上限且命中率持续低，或 unique 增长速度异常），一旦禁用则清空该字段缓存并后续直算。
  - disabled 的原因需要在 stats 日志中体现，便于线上解释。

（注：具体阈值与算法属于实现细节；实验阶段可选择保守策略，优先保证内存与不变慢。）

### 5) 可观测性：`scalim.performance` 可选输出 memo stats（一次/每次运行）

决策：

- 仅当 `SCALIM_EXP_CALL_BY_MEMOIZE_LOG_STATS` 启用时输出聚合日志，避免默认噪音。
- 日志载荷只包含聚合计数与字段 key，不包含依赖值本身；并控制 top-n，避免输出过大。

## Risks / Trade-offs

- **[风险] 用户误配导致“该缓存的字段没缓存/不该缓存的字段缓存”** → **缓解**：allow/deny 双开关，deny 优先；并在 stats 日志中输出“disabled/filtered”原因便于排障。
- **[风险] 缓存引入额外 CPU 开销而收益不及预期** → **缓解**：默认关闭；启用后仍具备字段级禁用；并提供统计日志帮助调整 allow/deny。
- **[权衡] 过滤策略越强（如正则、文件加载、动态表达式）越灵活，但也更难治理** → **取舍**：实验阶段只提供简单通配符 + CSV，保持可预期与低风险。

## Migration Plan

- 阶段 0（实验）：仅提供 `SCALIM_EXP_*` env；默认关闭。
- 阶段 1（稳定化，另行变更）：当能力证明 ROI 稳定，再评估迁移到非 `EXP` 前缀与更强的 profile/options 体系，并补齐文档站与示例。

## Open Questions

- 过滤匹配的粒度：是否允许同时匹配 `field_id` 与“别名/展示名”？（当前仅以 `field_id` 为准，最稳定。）
- stats 输出时机：仅 `pipeline_end` 输出一次是否足够，还是需要按批次输出（当前倾向仅一次，降低日志量）。

