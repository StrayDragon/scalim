---
depends_on: []
branch: sdd/c50-source-id-graph-refs
base_sha: ebb37794d5b6415bcd1669560d3b2c5495221165
checkpointed: false
---

# 字段图只存 source_id，策略只住目录

> Explore → propose（2026-08-18）。IR 合约 + r694 措辞；**不是** quick。
> 前序会话：[catalog resolve vs nested SourceIr](59580afc-5f49-4ea0-9f1d-f347c5b1f3fa)。
> notplan `source-catalog-ssot` 手递 **已吸收并删除**；档 1/2/3 与轻句柄路线 **作废**，改 source_id-only。落地 commit 是 `8273aa5b`。

## Why

`LookupChunking` 已按 `DemandIr.sources` 生效（`8273aa5b`），但字段图仍嵌完整 `SourceIr`。`replace()` overlay 后句柄指向旧对象。

`RowsReuse` 是同一洞的剩下一半：`load_step_data` 已 `resolve_lookup_source`，**单次 load 的 cache_mode 跟目录走**；`resolve_step_binding` / `can_group_by_relation` / `build_relation_signature` 仍读 `step.to_source.get_binding()`，**分组/跳过/cache key 跟编译期快照走**。

这违反已落地的 c40 优先级与 **r1004** 场景 `python-rows-reuse-overrides-yaml`（YAML `$rows.cache_mode=batch` + `RowsReuse.none()` MUST 禁用批次内 relation 复用）。现有 c40 单测只 assert 目录 IR 字段，没有执行 oracle，所以绿了但行为没兑现。

轻句柄（`SourceGraphHandleIr`）会变成第二套 Source 形状，新字段还会被塞进去，角色不清。终点是：**图只存 id，活对象只住目录**。新一组 overlay 加目录 + Python options，不改 `LookupStepIr` / `FieldIr`。

## Locked decisions（用户已拍板，不要重开）

| 决策 | 结论 |
|------|------|
| 优先级 | 该层 Python > 该层 YAML > 外层 Python > 外层 YAML > builtin。今天只有 source 层 = 显式 Python > YAML > builtin |
| 用户可见旋钮 | **不变**：仍 per-source `LookupChunking` / `SourceCache` / `RowsReuse`。不在本 change 发明 per-field 旋钮 |
| 图存储 | `LookupStepIr.to_source_id: str`；`FieldIr.source_id: str`。禁止嵌 `SourceIr` / 轻句柄 |
| overlay | 只 `replace(DemandIr.sources)`。禁止 rewire 字段图 |
| 构造 | wide in：仍可传入 `SourceIr`，出口只留 id（`DemandIr.from_irs` / compile intern） |
| 以后任一层 overlay | 新目录 `id → policy`，不是写回图边。field 层是槽位/模式，本 change 不实现具体 field 旋钮 |
| 正交 | `LookupChunking` 不级联 `batch_size`；未设 chunking ≡ `off()` ≡ 一次 loader 调用 |
| 路径 | 完整 SDD（propose → branch bind → specs landing → apply）。禁止在 `main` 改 live specs |

明确不做：轻句柄类型、`_rewire_embedded_source_refs`、为绿 demo 丢掉 miss/hit 区分、本 change 落地 per-field `RowsReuse`/`LookupChunking`。

## 代码事实（explore）

### 已对（catalog 读点）

- `apply_source_runtime_policies` 只 `replace(demand_ir, sources=...)`
- `ExecutionRuntime.resolve_lookup_source(step)` → `runtime.sources[source_id]`
- `load_step_data` 用 resolve 后的 source 再 `get_binding`
- `build_loader_sequences` 优先 `demand.sources[id]`
- YAML `LookupStepIr.bind` 恒 `None`（`conversion_relations._resolve_step_binding` return None）；binding 在 `SourceIr.bind` / `bindings`

### 仍错（图上读策略）

`src/scalim/utils/relation_signature.py` `resolve_step_binding` → 无 catalog。调用方：

- pipeline `can_group_by_relation` / `has_rows_binding` / streaming rows barrier
- load_ref executor 分组 skip（`load_ref_group_executed`）
- adaptive scheduler / strategy_unit / viz_schedule
- `build_relation_signature`（binding.cache_mode 进 signature）

### 图上读身份（改成 id + catalog 后仍合法）

这些读 `source_id` / `key` / `key.cast`，不是 overlay。改成 `to_source_id` 后从 `DemandIr.sources` / `runtime.sources` 取 key/cast：

- `LookupStepIr.get_to_key_or_source_key` / `get_to_fields_or_source_key`
- runtime / load_ref context / executor / relation_guardrails / adaptive.policy
- planning：`field.source.source_id`（sequences / deps / metadata / snapshots / operators / late_fields）
- `DemandIr.__post_init__` 校验字段引用的 source 存在

### 协议漏洞

`LookupSourceRefIrBase` 仍带 `lookup_chunk_size` / `lookup_chunk_parallel` / `get_binding`。`LookupStepIr.to_source` 类型允许把句柄当 live `SourceIr`。`FieldIr.source` 是 `Union[SourceIr, MainSourceIr]`，lookup 字段直接嵌完整 `SourceIr`。

### 机械面

`LookupStepIr(` / `to_source=` 出现在执行/规划大量单测（`test_executor_operator_load_ref.py`、`test_adaptive_*` 等）以及 `scalim_misc.example_report_ir`。作者态 `source["field"].join(...)`（`FieldRefIr` 持有活 `SourceIr`）与 **存盘 DemandIr 图** 分开：join 语法可继续用对象，compile/`from_irs` intern 进目录后图上只留 id。

## Specs（只读盘点；landing 在 propose 绑定分支）

| Spec | 关系 |
|------|------|
| `yaml-dsl-runtime-policy-boundary` r1004 | **已要求** Python `RowsReuse` 覆盖 YAML 并禁用批次内复用；执行未兑现。本 change 补行为 + 黑盒，不改优先级句子 |
| `ir-source-relations` r694 | signature 现写 `to_source`；应改为 `to_source_id` + catalog 解析的 binding。YAML `$rows.cache_mode: none` 场景仍有效；须加/收紧「Python overlay 后分组跟 Python」 |
| `ir-source-relations` r303 / r426 / r520 | lookup key / params 模板仍以 **目标 source 目录** 为准 |
| `execution-refloader-chunk-parallelism` | LookupChunking 已绿；勿回退 |
| 可能新 req | 图不得嵌 live `SourceIr`；overlay 只写目录；新 overlay 旋钮不得出现在 `LookupStepIr`/`FieldIr` |

`llman sdd context` 因 `LLMAN_SDD_INDEX_CHAT_MODEL` unset 不可用；以上为 `list --specs` + grep。

## What Changes

1. IR：`LookupStepIr.to_source_id`、`FieldIr.source_id`；`LookupSourceRefIrBase` 去掉 overlay 字段（或不再作为 step 字段类型）。
2. intern：`DemandIr.from_irs` / YAML compile 把传入的 `SourceIr` 放入 `sources`，图边只存 id。
3. 所有策略读点带 catalog；`resolve_step_binding(step, sources=...)`（或 `ExecutionRuntime.resolve_step_binding`）。空 catalog 单测必须显式给目录，禁止回退嵌套对象（嵌套对象将不存在）。
4. 黑盒：YAML `$rows.cache_mode=batch` + `RowsReuse.none()` → 同 relation 多字段 **不得** group skip（loader 次数真变）。反向 `none` + `RowsReuse.batch()` 必须能 group。禁止只 assert IR。
5. 文档/skills：新旋钮落点（source 目录 vs 将来 field 目录 vs demand）；禁止图边带 overlay。HANDOFF hash 改为 `8273aa5b` 并指向本 change。
6. 构造兼容：手写 `LookupStepIr(to_source=source)` 可在过渡期接受并提取 id；属性 `step.to_source` 删除或变成会误导的包装——**推荐直接改名 `to_source_id`**，一次机械迁移，不留轻句柄别名。

## 验收

- 现有 ch164 / ecommerce / big-data LookupChunking oracle 仍绿（miss vs hit）。
- 新 RowsReuse 执行 oracle 覆盖 r1004（Python 赢）。
- 类型上无法从 `LookupStepIr` 读到 `lookup_chunk_size` / overlay `cache_mode`。
- 无 YAML 新旋钮；无 per-field overlay API。

## Capabilities

### Modified

- `ir-source-relations`：r694 signature 改为 `to_source_id` + catalog binding；图不得嵌 live `SourceIr`
- `yaml-dsl-runtime-policy-boundary`：r1004 执行兑现（Python `RowsReuse` 真的禁用/启用分组）；不改优先级句子

### New（若 r694 放不下「图 vs 目录」不变量）

- `ir-source-catalog`：字段图只存 id；overlay 只写目录；新 overlay 旋钮不得出现在 `LookupStepIr`/`FieldIr`

## Impact

- 手写 IR：`LookupStepIr.to_source` / `FieldIr.source` 改为 `*_id: str`（breaking 属性名）。`DemandIr.from_irs` / compile intern 仍接受活 `SourceIr`。
- YAML authoring 不变。Python overlay 语义不变，分组行为与 r1004 对齐。
- 测试面：执行/规划大量 `to_source=` 机械改名；ch164 保持。

## Open questions — 已锁定（2026-08-18）

1. **过渡 API**：立即改名 `to_source_id` / `source_id`，不留 `to_source` 双字段。
2. **`to_field is None`**：保留含义「用 catalog 里该 source 的 key」。
3. **作者态 join**：`RelationIr.infer_lookup_path` 继续吃活 `SourceIr`；写入 `DemandIr` 时 intern。

## Triage

完整 SDD。理由：IR 存储形状 + r694 措辞 + r1004 执行兑现；跨 planning/execution/tests 机械改名。不是 `llman-sdd-quick`。

## HANDOFF fusion（原 `notplan/source-catalog-ssot/_HANDOFF.md`，目录已删）

| HANDOFF | c50 |
|---------|-----|
| LookupChunking 根因 / 禁 rewire / 与 `batch_size` 正交 / 未设 ≡ off | **已吸收**（Locked + design） |
| 已落地 runtime/docs/ch164/miss-hit 坑 / 复跑命令 | **已吸收**（design 回归约束；hash 改为 `8273aa5b`） |
| RowsReuse 分组仍读嵌套 binding；调用方列表 | **已吸收**（Why / 代码事实） |
| `LookupSourceRefIrBase` 类型漏洞 | **已吸收** |
| 空 catalog 回退 `step.to_source` | **作废**：无嵌套对象可回退；单测必须组目录。删除 `test_resolve_lookup_source_falls_back_to_nested_handle_when_catalog_empty` 的回退语义 |
| §5.3 身份字段留在句柄（key/cast/loader_spec） | **作废轻句柄**：身份从 catalog 读；`to_field is None` → catalog key |
| 档 1 quick / 档 2 剥策略 / 档 3 `SourceGraphHandleIr` | **作废**。本 change = 图只存 id，不是轻句柄 |
| r974 `$rows` 永不 chunk | **保持**；本 change 不改 chunk 语义 |
| 文件地图 | **已吸收**到 design / tasks |

测试 seam（已确认）：YAML compile+run / 现有 ch164 / `DemandIr.from_irs` intern。无新 `.feature`，不启用 `bdd:`。RowsReuse 黑盒走 pytest 执行，不加新 marimo 章。