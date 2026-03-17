## Context

现状(已实现,见 `openspec/specs/yaml-dsl-workflow/spec.md`):
- workflow YAML 仅支持 runs 列表 + 有限并发 + failure_policy + share_preload_cache。
- `run_workflow()` 当前在执行前会 **先编译所有 runs**,随后用线程池做队列并发。
- demand 侧 `{$init_var: <name>}`/`$init_var` 指令在 **编译期**解析: init_vars 需要在编译时给齐(见 `src/scalim/dsl/by_yaml/params_template.py`;命名修正在 `c0-yaml-init-vars`)。

为什么这会阻塞 DAG/ctx:
- 有依赖关系时,调度不再是“简单队列”;需要建图、拓扑调度与 cycle 检测。
- ctx 传递要求“上游完成后,下游才能拿到注入到 init_vars 的值”。但 init_vars 又在编译期使用,因此下游 demand 必须 **就绪后再编译**。

约束/相关方:
- 运行时需兼容 Python 3.6。
- 不扩展 CLI(仍是 Python 入口),workflow YAML 与 demand YAML 语义保持分离。
- scalim-viz 希望把 workflow 表达为可视化 DAG(节点/依赖/失败/耗时)。
- 文档/生成边界必须在实现前收敛(避免手改 `.gen.` 与 injected blocks,并提供 drift gate)。

本 design 目标:
- 给出推荐 MVP 方案 + 备选方案,并提供相对完整的 YAML 例子,用于后续讨论与收敛实现。

## Goals / Non-Goals

**Goals:**
- 为 `workflow.runs[*]` 增加依赖字段,使 workflow 可被解释为 DAG。
- 提供 run-scoped ctx(以 run_id 命名空间),允许把上游 ctx 注入为下游 run 的 init_vars(复用 `$init_var` 解析机制)。
- 静态校验: run_id 引用合法、无环,并在执行前 fail-fast。
- 并发下确定性:
  - 就绪节点选择顺序稳定
  - 返回 outcomes 顺序仍与声明顺序稳定对齐
- 不配置新增字段时保持旧行为(非 breaking)。

**Non-Goals:**
- ctx 里传递大体量 rows/dataset(不做“内存数据集图”)。
- 条件分支/动态生成 DAG/retry/cron 等工作流引擎能力。
- workflow 级的通用表达式语言(仅做最小必要的引用/注入)。

## Decisions

### 1) YAML authoring surface: run-level DAG + ctx → init_vars (Recommended)

在 `workflow.runs[*]` 上增加三个可选字段(字段名为提案,最终可讨论调整):

1) `depends_on: [run_id, ...]`
- 默认空列表。
- 依赖语义: 只有当依赖 runs **成功完成**后当前 run 才能进入可运行队列。

2) `init_vars: { <name>: <value> }`
- run-scoped,仅对该 run 生效。
- 与 Python 入口的 `init_vars` 合并(建议规则: run-scoped 覆盖同名 key)。

3) workflow ctx 引用值(仅在 workflow YAML 中使用)
- 推荐提供一个与 `$init_var` 同风格的“单键指令节点”用于引用 ctx:

```yaml
init_vars:
  users_csv_path:
    $ctx: extract_users.output_path
```

其中 `$ctx` 的值为 `<run_id>.<key>`:
- `<run_id>` 引用上游 run 的 id
- `<key>` 引用该 run 的 ctx key

ctx key 的 MVP 范围(自动注入,无需额外声明):
- `output_path`: 本 run 的 `RunResult.output_path`(单输出模式)
- `outputs`: 多输出时的 `ExecutionResult.outputs`(output_target_id → output_path)
- `total_rows`: 本 run 的输出行数
- `duration`: 本 run 耗时(秒)
- `demand_path`: 解析后的 demand 路径(便于调试/可视化)

ctx 值约束:
- MVP SHOULD 限定为 JSON-like(标量/小集合/映射),并对单 run ctx 设置 size 上限(例如按 JSON dump 字节数限制,防止误塞大对象)。

备选方案:
- A) `workflow.ctx` 顶层初始 ctx(常量) + `$ctx: workflow.<key>`: YAML 更自洽,但需要保留字/命名空间规则(避免与 run_id 冲突)。
- B) 不引入 `$ctx` 指令,改用结构化引用:

```yaml
init_vars:
  users_csv_path:
    from_ctx:
      run: extract_users
      key: output_path
```

优点是无需“点路径解析”;缺点是 YAML 更啰嗦且与现有 `$runtime` 风格不一致。

### 2) Scheduler: deterministic DAG scheduling

推荐在 runtime 内部引入一个“DAG 调度器”概念(仍保持外部 API 为 `run_workflow()`):

- 预处理(执行前 fail-fast):
  - 解析 runs,验证 id 唯一
  - 验证 `depends_on` 引用存在且不自依赖
  - cycle detection(建议 Kahn 拓扑排序;若剩余节点未被弹出则存在环,并在错误里输出一条可读的环路径/边集合)
- 调度规则:
  - 节点就绪条件: 依赖全部成功完成
  - 当多个节点同时就绪,选择顺序 MUST 稳定:
    - 推荐以 runs 声明顺序作为 tie-break(按 index 升序)
  - 并发: 就绪节点可按 `max_concurrency` 提交到线程池
- 返回顺序:
  - `WorkflowResult.outcomes` 顺序仍按 `workflow.runs` 声明顺序稳定对齐

### 3) Compilation strategy: compile on-ready (because init_vars are compile-time)

现实现是“先编译所有 runs 再执行”。在引入 ctx 注入后,下游 run 的 init_vars 可能依赖上游 run 的 ctx,因此推荐:
- demand 编译延迟到 run 进入可执行状态之后(依赖已满足且 init_vars 已解析)
- 仍可以在执行前做轻量的 fail-fast:
  - demand path 解析与存在性检查(可选 strict)
  - schema-only 校验(如果 workflow/demand 校验器可用)

备选方案(更复杂,不推荐作为 MVP):
- A) 两阶段编译: 先编译出“包含未解析 `$init_var` 指令”的 IR,运行前再注入并冻结。
  - 需要调整 `params_template` 的契约(目前 RuntimeDirectiveNode 明确要求编译期 resolve)。
  - 会把许多错误从“编译期”推迟到“运行期”,降低 fail-fast 能力。

### 4) Failure policy semantics under dependencies

`failure_policy` 在 DAG 场景需要补齐语义:

- `all_fail`:
  - 任一 run 失败即 workflow 失败
  - 未开始的 runs 标记为 cancelled
  - 已开始的 runs 允许继续完成(不做抢占式中断),但最终仍抛出 `WorkflowRunFailedError`

- `primary_only`:
  - 失败的 run 被记录,其后续“依赖它的节点”必须被标记为 cancelled(依赖未满足)
  - 与失败无依赖关系的分支继续执行
  - 最终返回 `WorkflowResult`,调用方可检查 errors/cancelled

### 5) share_preload_cache interactions (needs explicit decision)

现实现的 `share_preload_cache` 预检查要求“执行任一 run 前先编译全部 runs 并对比 preload 规格签名”。
在 DAG/ctx 场景下:
- 若某些 run 的 preload params 使用 `$init_var` 且该 init_vars 来自 `$ctx`,则其签名在 workflow 启动时不可得。

推荐的 MVP 处理方式(二选一,需要在实现前定案):
- A) **增量预检查**: 当某个 run 在真正执行前刚编译完成,再对其 preload 规格签名做一次“与已见签名对比”的 fail-fast 检查。
  - 保留“尽量早失败”的性质,但不再保证“在执行任一 run 前就完成全量预检查”。
- B) **约束组合**: 当 `share_preload_cache=true` 时,禁止使用 `$ctx` 驱动会影响 preload 签名的 init_vars(或更粗暴: 禁止任何 `$ctx` init_vars)。
  - 保留原 spec 的强 fail-fast,但限制可用性。

该点建议在提案讨论中明确,必要时通过 delta spec 补充约束或更新主规范。

### 6) Doc / generation boundary & drift gates (MUST)

需要在实现中明确哪些文件是“手写/生成/注入”,并用门禁防漂移:
- JSON Schema:
  - `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 为生成物,禁止手改
  - 通过 `scripts/gen-yaml-dsl-schema.py`/测试门禁保证 schema 与模型漂移可控
- docs:
  - `docs/doc/yaml-dsl/workflow.md` 为手写文档;任何 `.gen.`/注入块按既有治理规则更新
- gates:
  - `just gen-docs` 更新 docs-site 与注入块
  - `just qa` 回归测试/漂移门禁
  - `just openspec-check` 校验 OpenSpec 工件与 sanitize 规则

## Risks / Trade-offs

- [DAG + compile-on-ready 会改变错误暴露时机] → 将“路径解析/依赖合法性/cycle”保留为启动前 fail-fast;其余编译错误在节点首次就绪时暴露,并在错误中包含 run_id + demand_path。
- [ctx 过大导致内存与不确定性风险] → ctx 值限定为 JSON-like + size 上限;大型产物用“路径/句柄”而不是 rows。
- [share_preload_cache 与 ctx 组合导致预检查不完整] → 需要明确采用“增量预检查”还是“约束组合”,并在 spec 中写清楚。
- [并发下死锁/饥饿] → 仅用“就绪队列 + 线程池”模型,不做嵌套锁;ready 队列按 index 保持公平。

## Migration Plan

建议拆成可回归的增量里程碑(即使最终一次性落地也按此验收):

1) 仅引入 `depends_on` + cycle detection + DAG 调度(不做 ctx)
2) 引入 ctx 自动暴露(仅 meta) + run-scoped init_vars(仅字面量)
3) 引入 `$ctx` 引用 + ctx → init_vars 注入(带 JSON-like/size guardrails)
4) 处理 `share_preload_cache` 与 `$ctx` 的组合语义并补齐 spec/测试
5) 更新 docs/fixtures,并为 scalim-viz 提供可视化所需的稳定结构(如需要,另起 change)

## Open Questions

- `$ctx` 的 YAML 形态: `"$ctx": "run.key"` vs 结构化 mapping(可读性/可校验性/兼容性)？
- ctx 的自动导出字段集合是否需要可配置(例如只导出 `output_path`)？
- 是否需要 `workflow.ctx` 初始常量区(以减少 Python 入口注入),以及它的命名空间规则？
- `share_preload_cache` 在 DAG/ctx 下采用“增量预检查”还是“约束组合”(或两者兼容并可配置)？
- run_id 是否要收敛为更严格的命名规则(便于路径引用/可视化),以及对存量的兼容策略？

## MVP Examples

### Example A: Basic DAG (ordering under concurrency)

```yaml
workflow:
  runs:
    - id: A
      demand: ./a.demand.yaml
    - id: B
      demand: ./b.demand.yaml
      depends_on: [A]
    - id: C
      demand: ./c.demand.yaml
      depends_on: [A]
  options:
    max_concurrency: 8
    failure_policy: primary_only
```

### Example B: ctx → init_vars injection (path passing)

workflow:

```yaml
workflow:
  runs:
    - id: extract_users
      demand: ./extract_users.demand.yaml
    - id: report_users
      demand: ./report_users.demand.yaml
      depends_on: [extract_users]
      init_vars:
        users_csv_path:
          $ctx: extract_users.output_path
  options:
    max_concurrency: 2
    failure_policy: all_fail
```

downstream demand uses existing `$init_var`:

```yaml
name: report_users

main_source:
  source_id: users
  loader: myapp.loaders:load_users_csv
  params:
    path:
      $init_var: users_csv_path
```
