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
- 语义校验(启动前 fail-fast):
  - `runs` MUST 非空
  - `runs[*].id` MUST 非空且全局唯一
  - `runs[*].demand` MUST 为非空字符串
  - `options.max_concurrency` MUST 为整数且 >= 1(默认 `1`)
  - `options.failure_policy` 默认 `all_fail`
  - `options.share_preload_cache` 默认 `false`
- `demand` 路径解析:
  - 相对路径以 workflow 文件所在目录为基准
  - 可复用 `path_aliases`(由 Python 入口注入)解析 `"@/..."` 与 `"ALIAS:/..."`
    - 解析规则:
      - `"@/x/y.yaml"`: alias 为 `"@"`,相对片段为 `"x/y.yaml"`
      - `"ALIAS:/x/y.yaml"`: alias 为 `"ALIAS"`,相对片段为 `"x/y.yaml"`
      - alias 命中后按 `Path(path_aliases[alias]) / relative_segment` 拼接
    - 若 alias 未命中或值非法,立即报错(包含原始 `demand` 字符串与 run id)

2) **Python API 入口**
- 增加独立入口 `scalim.dsl.by_yaml.run_workflow(...)`(与现有 `scalim.dsl.by_yaml.run(...)` 并列),而不是让现有 `run()` 自动识别两种文件类型,避免破坏现有 demand-only 心智与错误诊断。
- 返回值契约(确保可编程检查且确定性对齐):
  - 约定返回/错误类型名:
    - `WorkflowResult`: workflow 执行结果对象
    - `WorkflowRunOutcome`: 单个 run 的 outcome(成功或失败)
    - `WorkflowRunError`: 单个 run 的可检查错误摘要(至少含 run id、demand 路径、异常类型与消息;可选 fingerprint)
    - `WorkflowRunFailedError`: `all_fail` 下抛出的异常包装(包含 run id 与 demand 路径,并以 `__cause__` 关联原异常)
  - `failure_policy=all_fail`:
    - workflow 失败即抛出异常,异常 MUST 包含 run id 与 demand 路径
  - `failure_policy=primary_only`:
    - 返回 `WorkflowResult`,其中 `outcomes` MUST 与 `workflow.runs` 一一对齐且顺序一致
    - 每个 outcome MUST 包含 run id、demand 路径、以及 `result`(成功)或 `error`(失败)

3) **并发模型**
- `max_concurrency` 仅控制 runs 粒度的并发(队列 + worker pool)。
- 返回结果顺序以 `runs` 声明顺序为准,以保证确定性。
- `all_fail` 在并发下的停止语义:
  - 一旦任一 run 失败,立即停止调度后续未开始的 runs
  - 尝试取消尚未开始的 runs(若执行器支持)
  - 已开始执行的 runs 允许继续完成或失败(实现不强制抢占式中断)

4) **共享 preload_forever cache**
- 抽象一个 workflow-scope 的 `PreloadCache` 容器(线程安全)。
- cache key 为 `source_id`;但写入/复用前必须校验 preload 规格签名一致:
  - loader 引用
  - 渲染后的静态 params(含 `preload_forever` 透传规则)
  - normalize 配置
  - key/lookup_cast 等影响 mapping 形状与 lookup 语义的关键字段
- 签名稳定性约束:
  - loader 引用必须先做归一化(相对引用 `.`/`..` 先根据 `yaml_path` 推导基准模块路径并归一化为绝对引用字符串)
  - params 渲染后的静态值必须可稳定签名;推荐仅允许 JSON-like 字面量:
    - `None`/`bool`/`int`/`float`/`str`
    - `list`/`tuple`/`dict`(递归,且 dict key 必须为 `str`)
  - 若出现其它对象(例如 `datetime`/`Decimal`/自定义对象),视为“签名无法计算”,按启动前预检查规则立即报错
- 启动前预检查:
  - 当 `share_preload_cache=true` 时,系统 MUST 在执行任一 run 之前完成冲突预检查:
    - 收集所有 runs 的 demand 中 `cache_mode: preload_forever` 的 source
    - 按 `source_id` 分组对比其 preload 规格签名
    - 若签名不一致,立即 fail-fast 报错,并指出冲突 runs 与差异字段(避免运行长时间后才失败)
  - 若签名无法计算(例如 params 渲染结果包含不可稳定签名的非字面量对象),系统 MUST 立即报错并指出来源 run 与路径。
- 并发下对单个 `source_id` 加锁,保证最多一次真实 loader 调用;其余等待复用结果。

5) **文档/生成边界与 drift gate**
- workflow schema 需要提供 JSON Schema 以支持 editor/schema validate,并由测试做漂移门禁。
- schema 输出路径建议: `src/scalim/dsl/by_yaml/schema/workflow.gen.json`(与 `demand.gen.json` 并列)。
- 对应生成脚本建议扩展: `scripts/gen-yaml-dsl-schema.py` / `scripts/gen-yaml-dsl-editor-schema.py`。
- 文档更新按 SSOT 生成规则执行,不手改 `.gen.` 与 injected blocks。

## Risks / Trade-offs

- [共享缓存导致“复用错了”出现静默错误] → 通过“签名一致性校验 + 冲突即报错”避免 silent reuse。
- [并发下缓存竞争与死锁] → 仅对单个 `source_id` 细粒度加锁;禁止在持锁期间执行其它 source 的加载。
- [workflow 输出路径冲突] → MVP 不做全局输出编排;默认由用户保证各 run 的 output 不冲突,必要时后续再扩展校验/路由。
