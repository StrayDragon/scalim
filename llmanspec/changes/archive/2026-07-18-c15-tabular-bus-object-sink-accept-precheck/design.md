# Design: c15-tabular-bus-object-sink-accept-precheck

## Decision

拆成三层，禁止再把「Excel 可写集合」当成「表格总线门禁」：

```text
1) Execution / relation : LookupKey = Hashable ; cell/runtime values = object
2) Tabular bus (InMemoryRows) : 表结构 SSOT；细胞 = object（原样持有）
3) Sink boundary : 每 sink 声明 accept set；默认写出时由库 fail；opt-in 预检可早死
```

`FieldValue` 降级为 **内建 Excel 推荐闭集**（文档 + opt-in 预检默认集合 + 兼容类型别名），不是 ROWS 运行时 SSOT。

**Apply 定案**：YAML `_ensure_field_value`（derived / literal / aggregate）**保留** `FieldValue` 窄校验——框架产出值仍限推荐闭集；loader→总线为 `object`。

## MVP 证据结论（2026-07-18）

脚本：`evidence/mvp_type_probe.py`（输出默认 `.tmp/evidence/rows-object-bus-mvp/type_probe.json`）。

| 值 | 今日 ROWS 门禁 | openpyxl | 含义 |
|---|---|---|---|
| naive 时间 / Decimal / bool | 过 | 过 | 窄路径不变 |
| `pd.Timestamp` | 过（子类漏放） | 过 | 闭集不自洽 |
| `np.datetime64` | 拒 | 拒 | 早死无额外价值 |
| `np.int64` | 拒 | **过** | 总线过严 |
| `np.float64` | 过（`isinstance float`） | 过 | 已静默漏放 |
| aware datetime | 过 | 拒(tz) | 失败本就在 sink |
| list/dict/object | 拒 | 拒 | 放宽后失败点下移即可 |

关联：`np.int64==1`、`np.datetime64==naive datetime`、`pd.Timestamp==naive datetime` 在探测环境 eq+hash 一致 → relation 不依赖 `FieldValue` 闭集。

## API / 运行时草图（实施时对齐）

### ROWS

- `InMemoryRows.rows: List[List[object]]`（或等价注解）；构造/`InMemoryRowsSink` **不再** `_is_field_value`。
- 仍校验：非空 header、行列宽一致。
- `in_memory_rows_to_in_memory_csv`：保持 `None→""` 其余 `str(value)`（显式转换，不是静默改 ROWS）。

### Sink accept set

- 每个内建 file/tabular sink 暴露稳定只读集合或谓词，例如：
  - Excel：对齐 openpyxl 可绑定集合（含现 `FieldValue` 推荐集；**不**声称接受 `np.datetime64` 除非实测可写）。
  - CSV：实质「任意 → `str`」（accept = object，规范化在写出）。
- 禁止在 accept 声明里承诺会自动 coerce 库类型。

### Opt-in 预检（Python SSOT）

- 建议挂点：`WorkflowRunOptions` / `DemandRunOptions` / sink 构造参数之一（闭集 Enum 或 bool），**默认 False**。
- 启用时：在首次写入目标 sink（或 composition 选定 sink）之前，对将写出的细胞按该 sink accept set 校验；失败 `TypeError`（信息含 field_id/type/sink）。
- MUST NOT 引入 YAML knobs。

### 失败清理（MVP）

已有较强基础：`save_openpyxl_workbook_atomic`、temp+replace、workflow staging。

MVP 必须补齐/锁定的缺口：

1. **最终路径**：save/replace 失败 → 最终文件不存在或保持旧版；Scalim temp 清理（已有测试可回归）。
2. **异常仍 `close()`**：`BaseRowSink.__exit__` 今日异常仍 commit——MVP 至少保证：若写出过程已判定类型/库错误，`close` 不得把坏结果原子替换到最终路径（失败则清理 temp）。更彻底的「exception → skip close」可作为 follow-up，避免一口吃成大行为变更。
3. **CSV 写入期 temp**：失败/未成功 close → best-effort 删 temp；不得 replace 到最终路径。
4. **Workflow staging `keep_on_failure`**：本 change **不改默认 True**（debug）；但 **publish 到最终用户路径** 失败时不得留下半残最终文件。文档写清「staging 残留 ≠ 最终半成品」。

## 与 c0 的关系

- **保留**：不静默 `str()`；不去 tz；naive 时间 Excel 日期语义；aware 与 openpyxl 同源报错。
- **修正**：c0 的「未知类型在 ROWS TypeError」改为「未知类型可进总线；默认在 sink 边界失败；opt-in 可早失败」。

## Trade-offs

| 选项 | 结论 |
|---|---|
| 继续扩 `FieldValue` 吞 numpy/pandas | **否决**（追不全） |
| 总线 object + sink accept + opt-in 预检 | **采用** |
| 默认开启预检 | **否决**（默认对齐库晚失败） |
| 静默 coerce `np.datetime64`→datetime | **否决**（另案显式 adapter） |
| 改 `keep_on_failure` 默认 | **否决（本 change）** |

## Future

- 显式 `value_adapter` / loader cast：`np.datetime64`→datetime、`Timestamp`→datetime。
- pandas/parquet sink 完整 accept 矩阵。
- `__exit__` 在 body 异常时 skip successful commit（更大 CM 语义变更）。
- `book_sheet_rows` 文档：承诺改为「原样透传」而非 FieldValue 闭集。
