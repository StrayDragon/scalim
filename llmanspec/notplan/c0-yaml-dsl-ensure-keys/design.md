# Design: yaml-dsl-ensure-keys

> **状态（2026-08-10）**：仅 ensure_keys。field-level `default` 决策与实现见归档 `2026-04-18-c0-yaml-dsl-ref-miss-default-cases`（现语法：`default: [{when: relation_miss, literal|call_by}]`），本文不重复。

## Context

落点在 **derived outputs finalize**：

- YAML `outputs[*].aggregate` → derived target → `AggregatingRowSink`（`execution/derived_outputs.py`）
- `close()`：`aggregator.finalize_rows()` → 下游 `write_batch`/`close`
- `aggregator.diagnostics()` 由 `output_composition/router.py` 收集进 meta/audit —— ensure_keys 统计应挂这里，不新开事件管线

约束：Python 3.6；schema 只改 SSOT + `just gen-yaml-dsl-schema`；`*.gen.*` / AUTOGEN 禁止手改。

相关但 **正交** 的已落地能力：LoadRef miss 上的 field `default`（`load_ref/flow.py`）。补全行上的「字段默认」走 `ensure_keys.defaults` + identity，**不**再走 field-level `default`。

## Goals / Non-Goals

**Goals**

- after_aggregate 按维度 source mapping keys 补缺失 group
- 未声明时语义不变；补全后顺序确定性可对拍
- preload_forever 维度源不二次 loader
- 严格校验 + diagnostics

**Non-Goals（v1）**

- detail output ensure_keys
- before_aggregate / 补全行参与 rank
- 改 main_source row universe / FULL OUTER JOIN
- 改动已落地的 field `default`

## Clarifications

### after_aggregate（v1）

先聚合再补行。成本低（通常补维度级行数）；不触发 lookup/compute 全链路。有 `rank_fields` 时补全行 rank 默认 `None`（见 Decision 排序）。

### before_aggregate / detail（defer）

语义与成本问题仍成立；另开 RFC，不在本草案。

## Decisions（ensure_keys）

### D1: output-level，且仅 derived（有 `aggregate`）

放在 `outputs[*].ensure_keys`，不放 `main_source`（多 output 的 group_by/字段不同）。

### D2: 期望键 = `from` source 的 mapping keys；`on` 可选且无歧义

- `from`: 必填 source_id  
- `on`: 可选；缺省 = `aggregate.group_by`；显式时必须完全一致（v1 不做异名/子集映射）

### D3: key 对齐用 derived output 的 key_normalization

与聚合 group key 同一口径（`raw` / `auto_str` 等），避免 int/str 误补。

### D4: 填充优先级

1. `ensure_keys.defaults.<out_field_id>`  
2. identity：`count`/`count_true`/`count_true_gte`/`count_distinct`/`sum` → `0`；`min`/`max` → `None`  
3. 其余（rank/post）→ `None`

### D5: 顺序

- 无 rank：按 group_by 稳定序 merge 插入  
- 有 rank：保持 finalize 原序；补全行确定性 append；rank 默认 `None`（除非 defaults 覆盖）

### D6: preload / SourceCache

- `from` 为 preload_forever（YAML 或 `SourceCache.preload_forever()`）→ MUST 读 PreloadCache，MUST NOT 再调 loader  
- 未 preload → 本 run 可加载一次，并按 `source_id` memoize keys（多 output 共享）  
- 文档推荐维度源 preload_forever；**不**为此新开 YAML 旋钮

### D7: 文档 / 生成边界

- SSOT：`schema_dsl/models/outputs.py`  
- 生成：`just gen-yaml-dsl-schema`  
- 合约：本目录 `specs/yaml-dsl-ensure-keys/spec.md`；转正后走 llman SDD live specs（须 Branch binding）

## Risks

- 维度键与 group key 空间不一致 → 编译期/文档强调对齐；运行期用同一 normalization  
- 非 preload 额外 IO → 提示 + run 内 memoize  
- rank 场景补全行 rank=`None` 可能不如 before_aggregate 直观 → v1 接受；强需求另 RFC

## Implementation Outline

1. Schema + validator + gen schema  
2. Compile ensure_keys 进 derived target  
3. Key provider（preload 优先）  
4. Finalize 后补行 + diagnostics  
5. 测试矩阵见 `tasks.md` §4–5  

建议落点：`derived_outputs.py`（包装 `finalize_rows`）或 `AggregatingRowSink.close` 紧邻 finalize；诊断字段并入现有 `AggregatorDiagnostics`。
