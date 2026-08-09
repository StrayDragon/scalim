# Evidence + inventory（c40）

> **开放盘点 + 实现核对 + 示例片段**。  
> **已拍板去向**以 `design.md` 为准（措施 I / II / III）；本文保留证据与片段，避免与设计决议双写冲突时以 design 为准。  
> 全 path 导出：`uv run python llmanspec/changes/c40-yaml-runtime-policy-boundary/export_schema_paths.py` → `.tmp/c40-yaml-field-inventory/`（不入库）。

## 分类用语（不用字母缩写）

| 说法 | 含义 |
|------|------|
| **宜留在 YAML（编排/内容）** | 换机房也应相同的图、字段、关联、loader 协议 |
| **宜收口到 Python（运行策略）** | 换部署配额、入口、宿主就会改的调优/策略 |
| **内容调用协议** | `params` 里怎么调 loader（`$keys` / `$rows`），勿与 source 粗缓存混称 |
| **已迁出 YAML** | 再写会 fail-fast，改走 Python |
| **能力已删除** | 不要复活 |
| **尚待证据** | 未决；本文不写死最终去留 |

「今日 Python 面」= 现在是否已有 typed 覆盖/入口。

---

## 一、已迁出 / 已删除（对照，非本轮新决议）

这些**不必再议进 YAML**。举例（主行分批，勿与下面的 `lookup_chunk_size` 混淆）：

```python
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, run

run(
    "report.yaml",
    options=DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
        runtime=DemandRunRuntimeOptions(batch_size=500),
    ),
)
```

同类已迁出：`guardrails`、demand `failure_policy`、`include_full_error_message`、`validate_unique_field_names`、`main_source.retry` / `sources.*.retry`、`meta`/`audit`、`write_defaults`、`workflow.options.*`。  
已删除能力：`budget`、旧 `outputs.*.container`、DedupBy / TwoStage 等。

本就不在 YAML：`parallel_mode`、`max_workers`、`parallelize_lookup_chunks`、`cache_pool`、`init_vars`、allowlist、observers 等。

---

## 二、可能要调整的配置（逐项：判断 + 真实片段）

下面每项都附**可运行形态的最小片段**（示意字段名可按项目替换）。

### 1. `sources.*.lookup_chunk_size`

**设计决议（见 `design.md` 措施 I）**：从 YAML **迁出**；Python `LookupChunking` typed oneof；本版本友好 fail-fast，0.11.* 清债。

**工作判断（证据）**：值常跟下游 SQL `IN` / HTTP payload / 供应商批次上限走；今日 **没有** chunk size 的 Python 覆盖，只有「片间并行」opt-in。

**YAML（现状）**：

```yaml
sources:
  customers:
    loader: "myapp.loaders:load_customers"
    key: customer_id
    lookup_chunk_size: 800   # 仅 keys 模式；省略 / 0 / null = 不分片
    params:
      ids: {$keys: {as: list}}
```

**Python（今日只能开并行，不能改 size）**：

```python
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    run,
)

run(
    "report.yaml",
    options=DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
        runtime=DemandRunRuntimeOptions(
            parallel_mode="adaptive",
            parallelize_lookup_chunks=True,  # 有分片后才有意义；size 仍读 YAML
        ),
    ),
)
```

**实现核对**：只出现在 `sources.*`（`main_source` 无）；`_resolve_lookup_chunk_size` 在 rows 模式 / `≤0` / `≥key 数` 时不分片。草案方向见 `design.md`（例如 per-source size 覆盖）。

---

### 2. `sources.*.cache_mode`

**设计决议（见 `design.md` 措施 II）**：YAML **保留** + Python `SourceCache` typed 覆盖。

**工作判断（证据）**：`preload_forever` 影响内存与冷启动；今日 **没有** per-source RuntimeOptions 覆盖；workflow `cache_pool` 已在 Python。

**YAML（现状）**：

```yaml
sources:
  dim_org:
    loader: "myapp.loaders:load_org_dim"
    key: org_id
    cache_mode: preload_forever   # 仅 none | preload_forever；默认 none
    params:
      as_of: {$init_var: as_of}   # preload 禁止 $keys / $rows
```

**Python（今日：workflow 缓存池，不是改 YAML 枚举）**：

```python
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunSecurityOptions,
    WorkflowRunOptions,
    run_workflow,
)
from scalim.dsl.yaml_dsl.workflow_types import (
    WorkflowCachePoolPreloadForeverUnlimited,
    WorkflowRuntimeOptions,
)

run_workflow(
    "workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
        ),
        runtime=WorkflowRuntimeOptions(
            cache_pool=WorkflowCachePoolPreloadForeverUnlimited(),
        ),
    ),
)
```

**勿与** 下面的 `$rows.cache_mode` 混称（枚举与语义都不同）。

---

### 3. `params` 里的 `$rows.cache_mode`

**设计决议（见 `design.md` 措施 II）**：YAML **保留** + Python `RowsReuse` typed 覆盖（与 `SourceCache` 拆类型名）。

**工作判断（证据）**：内容调用协议——控制同一 batch 内 relation 是否复用；schema 中 `params` 几乎开放 object，校验在 `params_template`。

**YAML（现状）**：

```yaml
sources:
  prices:
    loader: "myapp.loaders:load_prices"
    key: sku_id
    params:
      rows: {$rows: {cache_mode: batch}}   # 或 none：每字段各自调 loader
```

副作用 loader / 依赖可变 `batch_rows` 时用 `none`。

---

### 4. `resources.files.*.csv_file.encoding`

**设计决议（见 `design.md` 措施 III）**：YAML 保留 + 已有 override；**默认已是 `utf-8`**（钉测试即可）。

**工作判断（证据）**：多数随数据契约固定；也可能随宿主变。

**YAML**：

```yaml
resources:
  files:
    detail_csv:
      csv_file:
        path: {$init_var: out_root}
        encoding: utf-8
```

**Python 覆盖**：

```python
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    FileResourceOverride,
    ResourcesOverride,
    RunOverrides,
    run,
)

run(
    "report.yaml",
    options=DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
        outputs=DemandRunOutputOptions(
            overrides=RunOverrides(
                resources=ResourcesOverride(
                    files={"detail_csv": FileResourceOverride(encoding="gbk")},
                ),
            ),
        ),
    ),
)
```

---

### 5. `resources.books.*.xlsx.allow_formulas`

**设计决议（见 `design.md` 措施 III）**：YAML 保留 + 已有 override；**默认 `true`**；pathless 禁止。

**工作判断（证据）**：常静态；也可能按环境禁公式。

**YAML（有 path 的落盘 book）**：

```yaml
resources:
  books:
    report_xlsx:
      xlsx:
        path: {$init_var: out_root}
        allow_formulas: false
```

**Python 覆盖**：

```python
from scalim.dsl.yaml_dsl import (
    BookResourceOverride,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    ResourcesOverride,
    RunOverrides,
    run,
)

run(
    "report.yaml",
    options=DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
        outputs=DemandRunOutputOptions(
            overrides=RunOverrides(
                resources=ResourcesOverride(
                    books={"report_xlsx": BookResourceOverride(allow_formulas=False)},
                ),
            ),
        ),
    ),
)
```

---

### 6. `outputs[].write.include_header` / `header_fields_output_by`

**设计决议（见 `design.md` 措施 III）**：YAML 保留 + 已有 override；省略默认 **`include_header=true`**、**`header_fields_output_by=name`**（注意部分 RunOverrides 工厂默认 `field_id`，与 YAML 省略不同）。

**工作判断（证据）**：偏输出呈现；偶按消费者变。

**YAML**：

```yaml
outputs:
  - name: detail
    to: {file: detail_csv}
    write:
      include_header: true
      header_fields_output_by: name
    fields: [order_id, amount]
```

**Python 覆盖**：

```python
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    OutputOverride,
    OutputToOverride,
    OutputWriteOverride,
    RunOverrides,
    run,
)

run(
    "report.yaml",
    options=DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
        outputs=DemandRunOutputOptions(
            overrides=RunOverrides(
                outputs=(
                    OutputOverride(
                        name="detail",
                        fields=("order_id", "amount"),
                        to=OutputToOverride(file="detail_csv"),
                        write=OutputWriteOverride(include_header=False),
                    ),
                ),
            ),
        ),
    ),
)
```

---

### 7. `sources.*.normalize.*`（冲突/缺失策略等）

**工作判断**：更像宜留在 YAML（编排/内容）——改的是结果语义，换环境通常仍应一致；无部署配额证据则不进第一刀。

**YAML 示例**：

```yaml
sources:
  latest_status:
    loader: "myapp.loaders:load_status_rows"
    key: order_id
    normalize:
      index_by_key:
        key_field: order_id
        on_conflict: last    # error | first | last
        on_none: skip        # raise | skip
```

---

### 8. 相关但通常不「迁出」的内容协议：`$keys` / `$init_var`

**工作判断**：内容调用协议 / 已有 Python 注入——动态值用 `init_vars`，不必再造 YAML 策略键。

```yaml
main_source:
  source_id: orders
  loader: "myapp.loaders:load_orders"
  params:
    end_dt: {$init_var: end_dt}

sources:
  customers:
    loader: "myapp.loaders:load_customers"
    key: customer_id
    params:
      ids: {$keys: {as: set}}   # 或 as: list
```

```python
from scalim.dsl.yaml_dsl import (
    DemandRunOptions,
    DemandRunSecurityOptions,
    run,
)

run(
    "report.yaml",
    init_vars={"end_dt": "2026-08-01", "out_root": "/tmp/out"},
    options=DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"])),
    ),
)
```

---

## 三、仍宜留在 YAML 的大类（不逐叶展开）

编排图与身份、字段/关联、输出形状、`workflow.runs` / 资源 path 等——换环境应保持同一 demand。全 path 防漏见导出脚本（demand ≈ 198，workflow ≈ 19）。

---

## 四、开放问题

不在此写终局答案；评审选择题见 `design.md`「待评审只答」。
