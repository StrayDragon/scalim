# HANDOFF：Source 目录 SSOT / LookupChunking 真生效 / 轻句柄下一步

> 状态：**未转正**（不是 `llmanspec/changes/` active change）。  
> 代码已落在 `main`：`9c23d3f1`（ahead of origin）。  
> 本文件供下一会话直接接着做；不要当 live spec。

会话：[catalog resolve vs nested SourceIr](59580afc-5f49-4ea0-9f1d-f347c5b1f3fa)

---

## 1. 一句话

`LookupChunking` 写进了 `DemandIr.sources[id]`，但 LoadRef 读的是编译期嵌在 `LookupStepIr.to_source` 里的 `SourceIr` 快照，所以 `sized()` 看起来配置了、实际不分片。

**禁止**再走「覆盖 catalog 之后把字段图里的嵌套 `SourceIr` 全部 rewire 一遍」。那是打补丁，图一变就漏。

**已落地不变量**：`DemandIr.sources` / `ExecutionRuntime.sources` 是 live `SourceIr` 的 SSOT；字段图里的 `FieldIr.source` / `LookupStepIr.to_source` 只是身份 + key 形态的句柄；执行按 `source_id` 回目录。

---

## 2. 已拍板（不要重开）

| 决策 | 结论 |
|------|------|
| YAML `lookup_chunk_size` | 禁止；fail-fast → Python `LookupChunking`（c40 r1003） |
| `LookupChunking` vs `batch_size` | **正交**。前者切单次 keys LoadRef 的 `ids`；后者切主行流。 |
| 「没设 LookupChunking 就用 `batch_size`，再没有才全量」 | **不要做**。`ExecutionRequest.batch_size` 默认是 **1000**，一旦当 keys chunk 兜底，≥1000 unique keys 会默默分片、放大 RTT。未设 LookupChunking ≡ `off()` ≡ 一次 loader 调用。 |
| 字段图 rewire | **不要做**。已从 `apply_source_runtime_policies` 撤回。 |
| knobs 混用 / 优先级级联 | 用户确认 **A：保持正交**。 |

相关合约（只读，默认分支不要改 live specs）：

- `llmanspec/specs/yaml-dsl-runtime-policy-boundary/spec.toon` r1003（明确与 `batch_size` 正交）
- `llmanspec/specs/ir-source-relations/spec.toon` r694
- `llmanspec/specs/execution-refloader-chunk-parallelism/spec.toon` r974（`$rows` 永不 chunk）

---

## 3. 已落地（`9c23d3f1`）

### 3.1 运行时

- `apply_source_runtime_policies` **只** `replace(demand_ir, sources=...)`。
- `ExecutionRuntime.resolve_lookup_source(step)`：`runtime.sources[source_id]`，目录没有则回退 `step.to_source`（直接构造 IR、空 `runtime.sources` 的单测路径）。
- `load_step_data` 用 `runtime.resolve_lookup_source(step)`，不再 `source = step.to_source`。
- `build_loader_sequences` 优先 `demand.sources[id]`，否则才 `field.source`。

### 3.2 文档 / 示例 / 测试

- Public API 章：`notebooks/marimo/example_public_api_suite/chapters/ch164_public_api_lookup_chunking.py`  
  pytest：`tests/public_api/test_example_public_api_suite.py` 的 `chapter_ids` 含 `ch164`。  
  黑盒 oracle：Observer + Hook 订 `LOADER_CALL`，核 `chunk_offset` / `lookup_key_count` / `params["ids"]`。
- Demo：`ch010_yaml_dsl_ecommerce`、`ch050_workflow_demo_big_data_report` 同样用事件自证。  
  **坑**：`products` 同时是 `orders_to_products` 与 `orders_to_categories` 中间 hop → 第二次 LoadRef `cache_status=hit`，事件 `chunk_offset is None`。oracle 必须把 **miss 分片** 和 **hit** 分开，不能把 `None` 一律当「没分片」。
- Agent 卡：`agentdev/skills/scalim-yaml-dsl/references/lookup-chunking-guidance.md`
- 人类文档：user-guide §4.4.3、0.10.2、reading-guide、capability-matrix 等已加「何时用 / ch164」指针。
- 单测：
  - `tests/yaml_dsl/test_c40_policy_unit_coverage.py::test_apply_policies_updates_catalog_not_nested_field_handles`
  - `tests/execution/test_execution_runtime_key_normalization.py::test_resolve_lookup_source_prefers_catalog_over_nested_handle`
  - `...::test_resolve_lookup_source_falls_back_to_nested_handle_when_catalog_empty`

### 3.3 怎么复跑

```bash
uv run pytest -q tests/execution/test_execution_runtime_key_normalization.py \
  tests/yaml_dsl/test_c40_policy_unit_coverage.py \
  tests/yaml_dsl/test_c40_runtime_policy_boundary.py \
  tests/execution/test_loadref_chunk_parallelism.py --no-cov

uv run python -c "
from notebooks.marimo.example_public_api_suite.chapters.registry import run_selected_chapters
from notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.registry import run_selected_chapters as yaml_run
r = run_selected_chapters(chapter_ids=['ch164_public_api_lookup_chunking'])
r += yaml_run(chapter_ids=['yaml_dsl_ecommerce', 'workflow_demo_big_data_report'])
for x in r:
    print(x.passed, x.example_id, x.summary)
    x.raise_if_failed()
"
```

上次绿：ch164 `off=1 serial=4 parallel=4 ...`；ch010 `customers_chunks=[0, 5]`；ch050 `products_chunks=[0, 5, None]`（最后 `None` 是 hit，oracle 已按 miss/hit 拆开）。

---

## 4. 根因模型（给下一任）

编译 YAML → 同一份 `SourceIr` 既放进 `demand.sources` 又嵌进 `FieldIr.source` / `LookupStepIr.to_source`。  
`apply_source_runtime_policies` 对 catalog `replace()` 出**新对象**，嵌套句柄仍指向旧对象（`lookup_chunk_size is None`）。

```
DemandIr.sources["customers"]     ← overlay 后 live 策略（SSOT）
FieldIr.source / step.to_source   ← 编译期快照，不要当策略真源
ExecutionRuntime.sources          ← 从 demand.sources 拷进来
load_step_data                    ← 必须 resolve_lookup_source
```

Rewire 字段图 = 在 copies 之间同步，漏一条边就再静默失效。  
Resolve by `source_id` = 单一写点（catalog）+ 单一读点（resolve）。

---

## 5. 还没做完的洞

### 5.1 RowsReuse / binding（同类 bug，LookupChunking 已修、这条还在）

`src/scalim/utils/relation_signature.py`：

```python
def resolve_step_binding(step: LookupStepIr) -> Optional[BindingIr]:
    return step.bind or step.to_source.get_binding(binding_key)
```

没有 catalog。`RowsReuse` overlay 写在 `DemandIr.sources[id].bindings` / `.bind` 上，签名 / `can_group_by_relation` / LoadRef cache key 仍可能读嵌套快照。

`load_step_data` 里 binding 已是 `step.bind or source.get_binding(...)` 且 `source` 已 resolve，**真正 load** 可能已对；分组与 cache key 仍可能 stale。

调用方（都还走无 catalog 的 `resolve_step_binding`）：

- `build_step_signature` / `build_relation_signature`
- `can_group_by_relation` / `has_rows_binding`
- pipeline / adaptive scheduler / load_ref executor

### 5.2 协议仍允许从句柄读策略

`LookupSourceRefIrBase`（`src/scalim/spec/ir/_source_contracts.py`）带 `lookup_chunk_size` / `lookup_chunk_parallel` / `get_binding`。  
谁拿着 `step.to_source` 都可以当 live `SourceIr` 用——这就是原 bug 的类型漏洞。

### 5.3 其它仍读 `step.to_source` 的身份字段（可以留）

key / cast / `source_id` / `loader_spec` 属于图身份，不是 overlay 策略。不要为了「干净」误伤这些。

---

## 6. 下一步规划（用户要 C：轻句柄；下班前未选档）

用户确认：**先保持 knobs 正交，再做轻句柄 IR + RowsReuse 回目录**。  
档位未选，推荐顺序 **1 → 2**；**3 单开 SDD**。

### 档 1 — 执行收口 RowsReuse（推荐先做，quick 路径）

与 LookupChunking 同一不变量，不改 IR 类型。

- `resolve_step_binding(step, sources=...)` 或 `ExecutionRuntime.resolve_step_binding(step)`：catalog `get_binding` 优先，否则 `step.bind` / 句柄（空 catalog 测试回退）。
- 所有 `build_relation_signature` / grouping 热路径传入 catalog。
- 黑盒：YAML `$rows.cache_mode` + Python `RowsReuse.none()`，断言分组/复用事件或 loader 调用次数真变；**不要**只 assert IR 字段。
- SDD：行为修复现有 r694 / RowsReuse 语义，**默认分支不要改** `llmanspec/specs/**`。走 `llman-sdd-quick`。

### 档 2 — 嵌入时剥策略（物理上读不到 overlay）

编译进字段图时不要共享 catalog 对象：

- 句柄保留：`source_id`、`key`（+ 规划需要的 `loader_spec` / `normalize`）。
- 句柄清空：`lookup_chunk_size` / `lookup_chunk_parallel` / overlay 后的 `cache_mode` / `bindings[].cache_mode`。
- **不要**把 YAML 的 keys vs rows `mode` 剥掉——那是图语义，不是 runtime overlay。

仍接受用户 `LookupStepIr(to_source=full SourceIr)`，`__post_init__` 或 compile 出口剥一层。测试面相对档 3 小。

### 档 3 — 新类型 `SourceGraphHandleIr`（IR 构造面可能 breaking）

`LookupStepIr.to_source` / `FieldIr.source` 改为不含策略字段的具体类型。  
`LookupSourceRefIrBase` 拆成 identity vs policy。  
测试/notebook 里大量 `LookupStepIr(to_source=SourceIr)` 要跟。  
这是合约级，走 **`llman-sdd-propose`**（Branch binding 后再动 live specs）。不要在 `main` 上改 `llmanspec/specs/**`。

### 明确不做

- 不要把 `batch_size` 级联成 keys chunk。
- 不要恢复 `_rewire_embedded_source_refs`。
- 不要为了让 demo oracle 变绿而丢掉 miss/hit 区分。

---

## 7. 关键文件地图

| 角色 | 路径 |
|------|------|
| overlay 只打 catalog | `src/scalim/dsl/yaml_dsl/runtime/_internal/apply_source_runtime_policies.py` |
| resolve | `src/scalim/execution/executor/runtime/runtime.py` `resolve_lookup_source` |
| LoadRef 读策略 | `src/scalim/execution/executor/operators/load_ref/loader.py` `load_step_data` / `_resolve_lookup_chunk_size` |
| 规划用 catalog | `src/scalim/planning/loader_ordering/sequences.py` |
| 仍读嵌套 binding | `src/scalim/utils/relation_signature.py` `resolve_step_binding` |
| 协议漏洞 | `src/scalim/spec/ir/_source_contracts.py` `LookupSourceRefIrBase` |
| IR 注释（句柄 vs 目录） | `_demand.py` / `_fields.py` / `_relations.py` |
| 黑盒章 | `notebooks/marimo/example_public_api_suite/chapters/ch164_public_api_lookup_chunking.py` |
| 何时用 | `agentdev/skills/scalim-yaml-dsl/references/lookup-chunking-guidance.md` |
| fixtures | `packages/scalim-misc/src/scalim_misc/examples/public_api/_fixtures.py` |

---

## 8. 下一会话开场建议

1. 读本文件 + `git show 9c23d3f1`。
2. 问用户档 1 / 2 / 3（或 1+2）。默认建议 **档 1**。
3. 档 1：先写失败的 RowsReuse 黑盒（overlay 后分组/cache 行为），再改 `resolve_step_binding`，禁止弱化断言。
4. 档 3 才 `llman-sdd-propose`。
5. 未要求不要 commit `_HANDOFF.md`；要进 git 再说。
