## Context

现状:
- 单条 demand 的 `preload_forever` 语义在执行期缓存于 `ExecutionRuntime.preloaded_cache`,生命周期为单次 `engine.run()`。
- 多 demand 编排目前通过外部 Python glue 完成(例如为多 sheet workbook 依次运行多个 demand),缺少统一的 declarative 编排层与统一的缓存/失败策略。

约束:
- 不扩展 CLI(本 change 仅提供 Python 入口)。
- workflow 不引入“多 main_source 进同一 demand”的语义重构;保持 demand 心智模型为“单主流 + lookup sources”。
- 运行时需兼容 Python 3.6。

## Goals / Non-Goals

**Goals:**
- 定义可 schema validate、fail-fast 的 workflow YAML 语法,用于编排多个 demand 的执行(串行/有限并发)。
- 提供 Python 侧 workflow 运行入口,复用现有 `compile/run_ir` 链路执行每条 demand。
- 支持 `failure_policy` 统一控制:
  - `all_fail`: 任一 run 失败即失败
  - `primary_only`: 跳过失败的 run 继续执行,并返回可检查的错误集合
- 支持 `share_preload_cache=true` 时跨 runs 共享 `preload_forever` 小表缓存,并对规格冲突 fail-fast。

**Non-Goals:**
- workflow MVP 不内置 workbook/多输出组合能力(输出仍由每条 demand 的 `output` 或 Python overrides 决定)。
- 不做跨进程/跨天缓存持久化(仅同一次 workflow 进程内共享)。
- 不引入 DAG 依赖图/条件分支等复杂编排语义(仅队列 + 有限并发)。
- 不修改单条 demand 的既有执行语义。

## Decisions

1) **workflow YAML 结构**
- 采用顶层 `workflow:` 容器,其下包含:
  - `runs: [{id, demand}, ...]`
  - `options: {max_concurrency, share_preload_cache, failure_policy}`
- `demand` 路径解析:
  - 相对路径以 workflow 文件所在目录为基准
  - 可复用 `path_aliases`(由 Python 入口注入)解析 `"@/..."` 与 `"ALIAS:/..."`

2) **Python API 入口**
- 增加独立入口(例如 `run_workflow(...)`)而不是让现有 `run()` 自动识别两种文件类型,避免破坏现有 demand-only 心智与错误诊断。
- 返回值提供可编程检查:
  - `all_fail` 下抛出首个错误(包含 run id)
  - `primary_only` 下返回成功结果集合 + 错误集合(调用方可选继续处理)

3) **并发模型**
- `max_concurrency` 仅控制 runs 粒度的并发(队列 + worker pool)。
- 返回结果顺序以 `runs` 声明顺序为准,以保证确定性。

4) **共享 preload_forever cache**
- 抽象一个 workflow-scope 的 `PreloadCache` 容器(线程安全)。
- cache key 为 `source_id`;但写入/复用前必须校验 preload 规格签名一致:
  - loader 引用
  - 渲染后的静态 params(含 `preload_forever` 透传规则)
  - normalize 配置
  - key/lookup_cast 等影响 mapping 形状与 lookup 语义的关键字段
- 若同一 `source_id` 的签名不一致,fail-fast 报错并指出冲突 runs 与差异字段。
- 并发下对单个 `source_id` 加锁,保证最多一次真实 loader 调用;其余等待复用结果。

5) **文档/生成边界与 drift gate**
- workflow schema 需要提供 JSON Schema 以支持 editor/schema validate,并由测试做漂移门禁。
- 文档更新按 SSOT 生成规则执行,不手改 `.gen.` 与 injected blocks。

## Risks / Trade-offs

- [共享缓存导致“复用错了”出现静默错误] → 通过“签名一致性校验 + 冲突即报错”避免 silent reuse。
- [并发下缓存竞争与死锁] → 仅对单个 `source_id` 细粒度加锁;禁止在持锁期间执行其它 source 的加载。
- [workflow 输出路径冲突] → MVP 不做全局输出编排;默认由用户保证各 run 的 output 不冲突,必要时后续再扩展校验/路由。

