# Design: 图存 source_id，策略只住目录

## Context

`DemandIr.sources` 已是 overlay SSOT（`8273aa5b`），但 `LookupStepIr.to_source: LookupSourceRefIrBase` 与 `FieldIr.source: Union[SourceIr, MainSourceIr]` 仍嵌入完整对象。`replace()` 后句柄 stale。

`load_step_data` 已回目录；`relation_signature.resolve_step_binding` 没有。r1004 要求 Python `RowsReuse` 覆盖 YAML 并改变批次内复用，执行分组未兑现。

轻句柄会变成第二套 Source 形状。本设计：**图边只存 id**。

约束：Python 3.6；`src/scalim/` 相对导入；frozen dataclass + `replace`；不在默认分支改 live specs。

## Goals / Non-Goals

**Goals**

- 存盘 `DemandIr` 图：`to_source_id` / `FieldIr.source_id` 为 `str`
- overlay 只 `replace` 目录；图 id 稳定
- 策略读点一律 `catalog[id]`（含 binding / chunk / source cache）
- 身份读点（key、cast）`to_field is None` 时从 catalog 取 key；key 不是 overlay
- 作者态 `source["a"].join(source["b"])` 仍持有活对象；`DemandIr.from_irs` / YAML compile intern
- 立即改名，不留 `to_source` 别名
- 现有 per-source 旋钮与优先级不变；LookupChunking oracle 不回退

**Non-Goals**

- per-field overlay API
- 轻句柄类型
- rewire 嵌套对象
- `batch_size` 级联 keys chunk
- 启用仓库级 `bdd:` runner（除非用户另准）
- 改变 YAML authoring

## 两阶段对象

```
作者态（join / infer_lookup_path）
  SourceIr / MainSourceIr 活对象
        |
        v intern（from_irs / YAML compile）
存盘 DemandIr
  sources[id] = SourceIr          # 唯一活对象（含 overlay 字段）
  main_source = MainSourceIr
  fields[*].source_id = str
  lookup_steps[*].to_source_id = str
        |
        v overlay
  replace(sources[id])  only
        |
        v 执行
  runtime.sources = demand.sources
  resolve(step.to_source_id) -> SourceIr
```

`MainSourceIr` 不进 `sources`（现有不变量）。字段指向主源时 `source_id == demand.main_source.source_id`，读主源走 `main_source` 而非 catalog。

## intern 规则

`DemandIr.from_irs(sources=..., fields=..., main_source=...)`：

1. 收集 `SourceIr`：显式 `sources` 参数 ∪ 字段/步骤上误传入的活对象
2. 同一 `source_id` 必须是同一逻辑源；冲突 fail-fast
3. 写出 `fields.source_id` / `steps.to_source_id`
4. YAML compile 在 conversion 出口走同一 intern，不要在每个 step 里嵌 `to_source=to_source`

构造过渡：intern 入口可接受误传的 `LookupStepIr` 旧形——**不保留字段**。实现期直接改类型，测试机械改名。

## 读点

| 需要 | 函数 |
|------|------|
| live SourceIr（loader、chunk、bind.cache_mode、normalize） | `runtime.sources[step.to_source_id]`；planning 用 `demand.sources` |
| 主源字段 | `demand.main_source` if `field.source_id == main_source.source_id` |
| join key | `step.to_field` if set else `catalog[id].key.key` |
| default cast | `step.lookup_cast` or `catalog[id].key.cast` |
| binding | `step.bind or catalog[id].get_binding(key)` — **禁止**无 catalog 的 `resolve_step_binding(step)` |

`resolve_step_binding(step, sources, main_source=None)`：缺 `sources[id]` fail-fast（单测必须组目录）。无「回退嵌套句柄」。

## 协议

`LookupSourceRefIrBase` 不再作为 `LookupStepIr` 字段类型。若规划 infer 仍需 key+id，用作者态活 `SourceIr`，或最小 protocol **仅** `source_id` + `key`（**不得**含 `lookup_chunk_size` / `get_binding`）。推荐 infer 继续吃 `SourceIr`，存盘图不引用该 protocol。

## 以后任一层 overlay（本 change 只写进 spec/docs，不实现 field API）

```
更具体 Python > 更具体 YAML > 更外层 Python > 更外层 YAML > builtin
```

新旋钮：typed options + `apply_*` 写对应目录（source / 将来的 field / demand）。**禁止**把 overlay 字段加到 `LookupStepIr` / `FieldIr`。

## Specs landing（绑定分支）

- `ir-source-relations` r694：signature = `to_source_id` + from_fields + to_key + lookup_cast + **catalog 解析的** binding
- 新 req 或 r694 附句：图边 MUST NOT 嵌 live `SourceIr`；overlay MUST 只写 `DemandIr.sources`
- `yaml-dsl-runtime-policy-boundary` r1004：不改优先级；补执行口径指针（黑盒在 tests/notebooks，toon 场景可保持文档行）

无 `bdd:` 时场景留在 `spec.toon` `feature: true` 文档行（与现仓库一致）。

## 从 HANDOFF 吸收、且不得回退的约束

- LookupChunking 与 `batch_size` 正交；未设 ≡ `off()`。`ExecutionRequest.batch_size` 默认 1000，禁止当 keys chunk 兜底（HANDOFF §2）。
- `$rows` / `bind.mode=rows` 永不 chunk（r974）。
- ch164 / ch010 / ch050 oracle：**miss 分片 vs cache hit 的 `chunk_offset is None` 必须拆开**。
- `8273aa5b` 的空 catalog 回退 `step.to_source`：**删除**。`resolve_lookup_source` 只查 `runtime.sources[id]`，缺则 fail-fast。
- 回归复跑（apply 后仍须绿）：

```bash
uv run pytest -q tests/execution/test_execution_runtime_key_normalization.py \
  tests/yaml_dsl/test_c40_policy_unit_coverage.py \
  tests/yaml_dsl/test_c40_runtime_policy_boundary.py \
  tests/execution/test_loadref_chunk_parallelism.py --no-cov
```

ch164 / `yaml_dsl_ecommerce` / `workflow_demo_big_data_report` 事件自证保持。

## 关键路径（原 HANDOFF §7）

| 角色 | 路径 |
|------|------|
| overlay 只打 catalog | `apply_source_runtime_policies.py` |
| resolve source | `execution/executor/runtime/runtime.py` |
| LoadRef 策略 | `load_ref/loader.py` |
| 规划 catalog | `planning/loader_ordering/sequences.py` |
| binding/签名 | `utils/relation_signature.py` |
| 协议 | `spec/ir/_source_contracts.py` |
| intern | `spec/ir/_demand.py` `from_irs` + YAML conversion 出口 |
| ch164 | `notebooks/marimo/example_public_api_suite/chapters/ch164_public_api_lookup_chunking.py` |

## 风险

- 机械改名漏一处 `step.to_source` → 编译失败（比静默 stale 好）
- intern 漏收集某条边 → 目录缺 id，fail-fast
- 空 catalog 单测：必须改成带 `sources={id: source}`，不能靠嵌套对象
