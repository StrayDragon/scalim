# Evidence MVP — type probe

## 目的

对照三类边界：

1. 今日 `InMemoryRowsSink` / `FIELD_VALUE_TYPES` 门禁
2. openpyxl 直写可接受性
3. numpy/pandas 与 stdlib 的 `==` / `hash`（relation 假设）

## 运行

在仓库根目录：

```bash
uv run python llmanspec/changes/c15-tabular-bus-object-sink-accept-precheck/evidence/mvp_type_probe.py
```

默认写出：`.tmp/evidence/rows-object-bus-mvp/type_probe.json`（可丢弃；勿当 SSOT）。

可选：

```bash
SCALIM_C15_PROBE_OUT=/path/to/out.json uv run python .../evidence/mvp_type_probe.py
```

## 结论摘要（2026-07-18，uv 环境 openpyxl/numpy/pandas）

> **Apply 后**：`InMemoryRowsSink` 已放宽为接受任意 object；下表「ROWS 门禁」列为 **apply 前** 探测结果，用于说明为何要改。

| 值 | ROWS 门禁（apply 前） | openpyxl | 备注 |
|---|---|---|---|
| naive `datetime`/`date`/`time`/`timedelta` | OK | OK (`d`) | 窄路径 |
| `pd.Timestamp` | OK（`datetime` 子类） | OK | 闭集漏放 |
| `np.datetime64` | TypeError | ValueError | 早死无额外价值 → 现进总线、默认晚失败 |
| `np.int64` | TypeError | OK→int | 总线过严 → 现进总线 |
| `np.float64` | OK（`isinstance float`） | OK | 已漏放 |
| aware `datetime` / aware `Timestamp` | OK | TypeError(tz) | 失败在 sink |
| `list`/`dict`/`object` | TypeError | ValueError | 现进总线；写出仍失败 |

关联探测：`np.int64(1)==1`、`np.datetime64==naive datetime`、`pd.Timestamp==naive datetime` → eq 与 hash 均一致（本环境）。

完整机器可读结果以脚本输出 JSON 为准；本摘要便于 PR/评审共享。
