## Context

`scalim.vendor.literich` 当前仅用于 CLI/调试/可观测性输出的 “表格/面板” 渲染（`Table`/`Panel`），并被以下运行时代码引用：

- `src/scalim/ob/metrics.py`
- `src/scalim/ob/presets/logs.py`（pretty logging）
- `src/scalim/ob/presets/execution_trace.py`
- `src/scalim/ob/presets/memory.py`
- `src/scalim/ob/presets/relations.py`
- `src/scalim/ob/presets/performance_presentation.py`

继续维护该 vendor 会扩大 `src/scalim/vendor/` 的运行时表面（需要长期兼容 Python 3.6），且其可被直接 import（`scalim.vendor.literich`）容易被下游误认为“事实公共 API”，导致后续演进与删除成本升高。

本变更希望移除 `literich`，并把相关 console 输出统一收敛为稳定、可 grep、dependency-free 的纯文本 logger 输出。

**约束（本变更的硬约束 / 口径）**

- **Python 3.6 runtime**：`src/scalim/` 的实现 MUST 保持 Python 3.6 兼容。
- **零新增运行时依赖**：console 输出 MUST 仅依赖标准库 `logging`（不得引入 `rich` 等新依赖；不得继续依赖 `scalim.vendor.literich`）。
- **日志治理一致性**：遵循 `framework-logging` 规范：运行时路径 MUST 通过 logger 输出（禁止 `print(...)`），并使用稳定前缀 `[scalim] <subsystem>:`。
- **console 输出稳定性**：console 报告 MUST 为“逐行（line-oriented）”文本；不得依赖表格对齐/等宽字体/Unicode 宽度；字段表达以 `k=v` 为主（key 排序稳定，`None` 省略）。
- **只改展示、不改指标语义**：指标口径（计数/耗时/命中率等）不变；`json/csv` 报告结构不变；仅 `console` 展示形态发生变化。
- **破坏性变更**：移除 `scalim.vendor.literich` 不做兼容层/弃用期（一次性升级全仓引用）。

文档/生成治理边界（仅在需要触及 docs 时适用）：

- 任何包含 `.gen.` 的文件为生成物，禁止手改；应修改 SSOT 并运行 `just gen-docs`。
- 任意 `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` 区块为注入块，禁止在区块内手改；应修改 SSOT 并运行 `just gen-docs`。

## Goals / Non-Goals

**Goals:**

- 移除 `src/scalim/vendor/literich/`，并删除/替换其测试与文档入口（`src/scalim/vendor/README.md`）。
- 将受影响模块的 console 输出收敛为稳定的“前缀 + kind + `k=v`”逐行文本（面向 grep / 日志采集）。
- 确立并固化输出“展示约束”（见本设计与增量 specs），避免未来再引入表格对齐/渲染器依赖。
- 回归策略：测试仅断言关键信息/字段存在（不依赖对齐/边框字符），并确保 `pytest capsys` 可捕获输出。

**Non-Goals:**

- 不重新实现 `rich` 或任何“表格渲染器”等价物；不引入颜色/样式化输出。
- 不引入新的配置项来在新旧格式间切换（不做兼容双写）。
- 不调整性能/关联等指标的统计口径（仅改 console 展示）。

## Decisions

1) **Canonical line format：稳定前缀 + kind + `k=v`**

所有 console 输出统一为：

`[scalim] <subsystem>: <kind> <k=v, k2=v2>`

其中：

- `<subsystem>` 使用 `scalim._internal.loggingx.prefix(subsystem)` 产生（例如 `relations`、`performance`）。
- `<kind>` 为稳定 token（例如 `summary`、`per_source`、`stage`、`loader`、`samples`）。
- `k=v` 使用 `scalim._internal.loggingx.format_kv(...)` 生成（key 字典序稳定；`None` 省略）。

2) **Stable keys（按模块定义最小稳定键集合）**

以 `relations` 与 `performance` 为主（其它 summary 类输出遵循同一风格）：

- relations summary（kind=`summary`）：`total_lookups`、`hits`、`misses`、`null_keys`、`type_errors`、`hit_rate`
- relations per source（kind=`per_source`）：`source`、`total`、`hits`、`misses`、`null_keys`、`type_errors`、`hit_rate`
- relations samples（kind=`type_mismatch_samples`）：`showing`（后续逐行输出样本，保持行级 `k=v`）
- performance summary（kind=`summary`）：`total_duration_s`、`total_rows`、`throughput_rows_s`、`batch_count`、`avg_batch_duration_s`（可选追加 `peak_memory_mb` / `memory_increase_mb`）
- performance stage breakdown（kind=`stage`）：`stage`、`duration_s`、`percent`
- performance loader stats（kind=`loader`）：`loader`、`calls`、`records`、`avg_time_s`

3) **实现方式：小型内部 helper + 全仓替换**

为避免各 observer 重复拼接字符串、且便于未来做一致性校验，引入小型内部 helper（例如 `src/scalim/ob/_internal/console_report.py`）集中封装：

- line building（prefix/kind/kv）
- 常用格式化（百分比、秒、可选字段）

该 helper 属于 internal 实现，应遵循 public-surface 治理约束（例如 `_internal` 模块 `__all__` 为空，避免泄漏为公共 API）。

4) **测试策略：只断言“信息存在”，不锁定对齐/边框**

- 删除 `tests/test_literich.py`，新增针对新 console 输出的最小回归：
  - 断言包含前缀、kind token 与关键键名（例如 `summary` / `total_lookups=` / `hit_rate=`）
  - 不对齐、不检查 box drawing 字符

5) **治理：阻止 `scalim.vendor.literich` 回流到用户材料**

在用户材料门禁脚本（`scripts/check-user-material-import-boundaries.py`）中加入对 `scalim.vendor.literich` 的硬禁止 token（仅该模块，不泛化到整个 `scalim.vendor.*`），以防未来又把已删除模块写进 docs/skills/notebooks。

## Risks / Trade-offs

- [输出变“没那么漂亮”] → 通过 kind token + 稳定 key 集合确保可读性与可检索性；必要时后续可在不破坏契约的前提下增加可选的“额外行”（但不引入渲染器依赖）。
- [下游脚本解析旧表格字符会断] → 作为 BREAKING 变更处理；新格式改为 `k=v` 更适合机器解析与日志采集。
- [样本/详情行过多导致刷屏] → 样本输出保持有界（例如 `showing=N` 且仅输出前 N 条），其余维持 summary/per_source。

## Migration Plan

1. 删除 `scalim.vendor.literich` 与其测试；更新 `src/scalim/vendor/README.md`。
2. 逐个替换受影响 observer/presentation 的 console 输出，统一为 prefix + kind + `k=v` 逐行文本。
3. 增补/更新测试（只断言关键信息存在），并在 `just qa` 下验收。
4. 运行 `just openspec-check` 确保 OpenSpec 工件可 sanitize/validate。

## Open Questions

- 是否需要为 console 输出提供“按行输出的稳定 schema 文档”（例如 keys 列表）以支持下游采集？（本变更先以 specs 固化最小键集合，不引入额外文档生成。）
