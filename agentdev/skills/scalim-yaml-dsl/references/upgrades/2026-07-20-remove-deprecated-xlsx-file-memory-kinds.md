# 2026-07-20: remove-deprecated-xlsx-file-memory-kinds

## 变更摘要

BREAKING：硬删 YAML book 过渡期别名 `xlsx_file` / `xlsx_memory`（含 `xlsx_memory.export_xlsx`）。唯一 authoring SSOT 为 `resources.books.<id>.xlsx`（可选 `path`）。

同时：

- 运行时身份仅 **pathful / pathless**（不再以 `kind=xlsx_file|xlsx_memory` 字符串为 IR/runtime 业务 SSOT；`BookConfig.kind` 恒为空串，override 传入 `kind` 会 fail-fast）
- YAML `observability.*` 由 warning+忽略升级为 **fail-fast**
- 公开类型别名 `RowId` / `RowIdSeq` / `RowIdList` 已移除 → 使用 `BusinessKey`

**保留（调用面不变）**：`RunOverrides.xlsx_file_single_sheet(...)` 等工厂函数名与签名；内部已改为 pathful / `xlsx.path` 等价构造。

对应 llmanspec change: `llmanspec/changes/archive/2026-07-20-c999-remove-deprecated-xlsx-file-memory-kinds/`

上游：`2026-07-13-unified-xlsx-book-kind.md`、`2026-07-13-normalize-xlsx-book-ir-path-presence.md`

## Migration Checklist

### 1) 落盘 book

Before（现已失败）：

```yaml
resources:
  books:
    report:
      xlsx_file:
        path: ./out
```

After：

```yaml
resources:
  books:
    report:
      xlsx:
        path: ./out
```

### 2) 内存总线

Before（现已失败）：

```yaml
resources:
  books:
    scratch:
      xlsx_memory: {}
```

After：

```yaml
resources:
  books:
    scratch:
      xlsx: {}
```

### 3) 旧 export 别名

Before（现已失败）：

```yaml
xlsx_memory:
  export_xlsx: {path: ./out}
```

After：

```yaml
xlsx:
  path: ./out
```

### 4) Python 工厂（无需改调用）

```python
RunOverrides.xlsx_file_single_sheet(
    output_root="./out",
    fields=["a", "b"],
    sheet="detail",
)
```

名称与签名保持稳定；等价于声明 pathful `xlsx.path`。

### 5) 其它 BREAKING

| 旧写法 | 新写法 |
|---|---|
| YAML `observability: ...` | Python/CLI runtime observers / hooks |
| `from scalim.typedefs import RowId` | `BusinessKey` |

## 明确不做

- 不删除 pathless 内存总线语义
- 不合并 workbook/sheetbook 实现模块
- write/budget 不回流 YAML
- 不重命名 `xlsx_file_single_sheet`
