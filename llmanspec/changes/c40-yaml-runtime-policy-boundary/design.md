# Design: YAML vs Python policy boundary（c40）

## 目标态

- YAML：可移植的编排、资源身份、内容/数据流语义。  
- Python：部署/入口可变的运行策略；**配置面优先类型化 oneof**（选一种策略类型 → 只出现该类型字段），避免平铺旋钮让人猜约束。  
- 证据与示例片段：`evidence-notes.md`。本文件为**已拍板方向**（可继续逐项细化签名）。

## 配置面原则：类型化 oneof（全切片共用）

用户先选 **策略种类**，再只填该种类需要的字段：

| 反例（避免） | 正例（目标） |
|--------------|--------------|
| 平铺 `lookup_chunk_size=800` + `parallelize=True` + 文档里一堆「何时无效」 | `LookupChunking.sized(size=800)` / `LookupChunking.off()`；并行是 sized 上的可选能力或并列 typed 策略 |
| 字符串 `"preload_forever"` 与 `$rows` 的 `"batch"` 同叫 cache_mode | 两套 **不同类型**（source 缓存策略 vs rows 复用策略），API 名与类型名拆开 |

闭集策略值走仓库 Hard Rules：`StrEnum` SSOT；构造入口只收 Enum/策略对象，配置/YAML 宽进后归一 builtin `str` 再存（若该键仍留 YAML）。

---

## 措施 I — 从 YAML 迁出（本版本友好拒绝；0.11.* 批量清债）

**语义**：authoring YAML **不再支持**声明该字段。本版本（0.10.* 线）validate/compile **fail-fast + 友好迁移提示**（指向 Python typed API）。历史「假装合法字段」的债务在 **0.11.*** 与其它 breaking 一并硬删/收紧（私有使用方可控升级；公开后再做可维护的 warn→error 窗）。

### I.1 `sources.*.lookup_chunk_size`

| 项 | 决定 |
|----|------|
| YAML | **迁出**：再写 → 本版本友好错误（勿静默忽略） |
| Python | **唯一 authoring 面**：typed oneof（示意，签名可再磨） |

```python
# 示意 — 落地前可改名，但必须保持「选类型再填字段」+ 并行仅挂在 sized
LookupChunking.off()
LookupChunking.sized(size=800)                  # 串行分片
LookupChunking.sized(size=800, parallel=True)   # 片间并行（嵌在 sized 上）
```

- 挂载：`DemandRunRuntimeOptions.lookup_chunking: Mapping[source_id, LookupChunking]`。  
- 未配置 source：等价今日「不分片」。  
- 旧 `parallelize_lookup_chunks` / `max_chunk_workers`：**收进 sized**（`parallel=` / worker 上限字段）；禁止继续推荐平铺布尔为唯一入口。  
- 勿与已迁出的 demand `batch_size`（主行分批）混谈。

**YAML 错误提示应像**：

```text
sources.customers.lookup_chunk_size was moved out of YAML authoring.
Configure LookupChunking via DemandRunOptions.runtime (...); see upgrade notes.
```

---

## 措施 II — YAML 保留 + Python 可覆盖

**优先级（写进合约）**：**显式 Python 覆盖 > YAML 声明 > builtin 默认**。禁止静默忽略 YAML。

### II.1 `sources.*.cache_mode`

| 项 | 决定 |
|----|------|
| YAML | **保留** `none` \| `preload_forever`（默认 `none`） |
| Python | per-source **typed 覆盖**（与 `$rows` 拆类型名） |

```python
SourceCache.none()
SourceCache.preload_forever()
# options 上: source_cache={"dim_org": SourceCache.preload_forever()}
```

与 workflow `cache_pool`：pool 仍只消费 preload 类 source；文档一句话——**YAML/覆盖决定「是否 preload」；pool 决定「跨 run 是否共享」**。

### II.2 `params` 内 `$rows.cache_mode`

| 项 | 决定 |
|----|------|
| YAML | **保留** 指令 `$rows: {cache_mode: batch\|none}`（默认 `batch`） |
| Python | **可覆盖**（typed；命名避开与 SourceCache 撞车） |

```python
RowsReuse.batch()   # 批次内 relation 复用
RowsReuse.none()    # 每字段各自调 loader
# 挂载（已拍板）: DemandRunRuntimeOptions.rows_reuse={"prices": RowsReuse.none()}
```

仍属内容调用协议语义；与 II.1 **禁止**共用一个平铺 `cache_mode` 字段。

---

## 特别调整 III — 已有 overrides；核对默认值

均 **保留 YAML** + 已有 `RunOverrides` 覆盖面；本切片重点是**默认值确认**与文档/类型体验对齐（需要时可把 override 也收成 typed oneof，但不强行迁出 YAML）。

### III.1 `resources.files.*.csv_file.encoding`

| 核对 | 结果 |
|------|------|
| Schema / `FileCsvFileConfig` / `DEFAULT_OUTPUT_ENCODING` | **已有默认 `utf-8`** |
| 解析 | workflow/demand 路径空串会回落到 `DEFAULT_OUTPUT_ENCODING` |
| Python | `FileResourceOverride.encoding` 已可覆盖 |

**结论**：无需新加「默认可选配置」能力；落地时补测试钉死「省略 encoding ≡ utf-8」，文档与 skill 写明。

### III.2 `resources.books.*.xlsx.allow_formulas`

| 核对 | 结果 |
|------|------|
| Schema | **默认 `true`**；文案：不可信输入显式 `false` |
| 约束 | **pathless book 禁止**该字段 |
| Python | `BookResourceOverride.allow_formulas` 已可覆盖 |

**结论**：默认已存在（布尔，不是 utf-8）。本切片：文档钉默认 + pathless 错误；可选 typed `ExcelFormulas.allow() / .deny()` 包一层 override（非必须）。

### III.3 `outputs[].write.include_header` / `header_fields_output_by`

| 核对 | 结果 |
|------|------|
| `include_header` | 省略时运行默认 **`true`**（`DEFAULT_OUTPUT_INCLUDE_HEADER`） |
| `header_fields_output_by` | schema/常量默认 **`name`**（`DEFAULT_OUTPUT_HEADER_BY`） |
| Python | `OutputWriteOverride` 已可覆盖 |

**结论**：默认已存在。本切片将 `RunOverrides` **工厂**默认 `header_fields_output_by` 从 `field_id` **改为 `name`**，与 YAML 省略 / `DEFAULT_OUTPUT_HEADER_BY` 对齐；upgrade 注明行为变化并扫调用方。

> 关于「4/5/6 默认都是 utf-8」：仅 **encoding** 适用 utf-8；5/6 为布尔/枚举，上表已给出实际默认。

---

## 版本与兼容窗

| 阶段 | 行为 |
|------|------|
| **本切片 / 0.10.\*** | I.1：YAML 写 `lookup_chunk_size` → **友好 fail-fast**；Python typed API 上线；II/III 覆盖与默认钉死 |
| **0.11.\*** | 与其它 YAML 债务一并：**硬移除**残留解析分支/历史兼容（私有仓可控升级） |
| **公开后** | 再引入可维护的 warn→error 迁移窗（本切片不实现） |

## 非目标

- 复活 `budget` / `write_defaults` / Dedup / TwoStage  
- 新增 YAML 并行键  
- 把 `$rows.cache_mode` 与 `sources.*.cache_mode` 收成同一个平铺字段  
- 本切片改公开 PyPI 的长期双轨 warn 窗  

## 交付面（落地时）

1. schema/validator：I.1 拒绝 + 文案；II/III 默认与覆盖测试  
2. typed oneof API + Enum SSOT + 覆盖优先级测试  
3. capability-matrix / user-guide / skill / upgrade 卡  
4. 若改 MUST → `change start` + specs landing  

## 已拍板细项（2026-08-09）

| # | 抉择 | 含义 |
|---|------|------|
| 1 | **A** | 片间并行嵌在 `LookupChunking.sized(...)` 上（`off` 无法表达并行） |
| 2 | **A** | `RowsReuse` 挂在 `DemandRunRuntimeOptions` per-source |
| 3 | **A** | `RunOverrides` 工厂默认 `header_fields_output_by` 对齐 YAML 省略默认 **`name`** |
| 4 | **升本 c40** | 改 live MUST → `change start` + specs landing → apply |

### API 形态（随拍板收紧）

```python
# I — YAML 禁止 lookup_chunk_size
LookupChunking.off()
LookupChunking.sized(size=800)                 # 默认串行分片
LookupChunking.sized(size=800, parallel=True)  # 仅 sized 可并行；须 adaptive 等既有护栏

DemandRunRuntimeOptions(
    lookup_chunking={"customers": LookupChunking.sized(800, parallel=True)},
    source_cache={"dim_org": SourceCache.preload_forever()},
    rows_reuse={"prices": RowsReuse.none()},
)
# 覆盖优先级: 显式 Python > YAML > builtin
# 旧 parallelize_lookup_chunks: 迁移到 sized(..., parallel=True)；残留平铺布尔本切片 deprecate/友好提示（细节 apply 时定）
```

III.3：`RunOverrides.csv_file` / `xlsx_file_single_sheet` 等工厂的 `header_fields_output_by` 默认改为 `"name"`，与 `DEFAULT_OUTPUT_HEADER_BY` 一致；加回归测试。
