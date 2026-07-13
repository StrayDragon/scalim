# Design — add-unified-xlsx-book-kind

## 初衷（别名 → 统一 `xlsx`）

```text
YAML authoring（过渡期）
  xlsx_file: {path: P}              ──warning──►  内部正规化：xlsx + path=P
  xlsx_memory: {}                   ──warning──►  内部正规化：xlsx 无 path（总线）
  xlsx_memory + export_xlsx.path=P  ──warning──►  内部正规化：xlsx + path=P
  xlsx: {} / xlsx: {path: P}        ───────────►  同上（新 SSOT，无旧 kind warning）
```

- **对外 SSOT**：只有一种书类型 `xlsx`；差别只在 **有没有 `path`**。
- **旧 kind**：deprecated **别名**，必须 warning，行为等价，**本 change 不删解析**。
- **硬删旧名**：下游迁移完成后另开 BREAKING（warning→error→delete）。

本 change **不**因改名降低 RSS；内存见下文「可维护性与内存」。

## YAML vs Python（硬边界）

| 层 | 允许 | 禁止 |
|---|---|---|
| **YAML** | book **identity**：选 `xlsx`（或过渡期旧别名）；可选 `path`；可选 `allow_formulas` | `write_defaults` / `budget` / 优化档位 / deprecation 开关 / 新 `xlsx` 上的 `export_xlsx` |
| **Python** | `ResourcesPolicy` / `BookWritePolicy` / `BookBudgetPolicy`；日后 seal/spill/profile | 把上述政策写回 YAML books |

## Target authoring

```yaml
books:
  scratch:
    xlsx: {}                 # 无 path = 内存总线
  report:
    xlsx:
      path: ./out            # 有 path = 版本化落盘
      allow_formulas: false
```

```python
# 写入/预算仍在 Python（示例形状，非本 change 新增 API）
WorkflowRunOptions(
    resources_policy=ResourcesPolicy(
        books={
            "scratch": BookResourcePolicy(write=BookWritePolicy(...)),
            "report": BookResourcePolicy(write=BookWritePolicy(...)),
        }
    )
)
```

## 迁移映射

| 旧写法 | 正规化结果 |
|---|---|
| `xlsx_file: {path: P}` | `xlsx` + path=P（内部「有 path」后端） |
| `xlsx_memory: {}` | `xlsx` 无 path（内存总线） |
| `xlsx_memory: {export_xlsx: {path: P}}` | `xlsx` + path=P + **旧写法** deprecated warning |

## Deprecation（本 change 必须可测）

1. 使用 `xlsx_file` / `xlsx_memory`（含旧 `export_xlsx`）时：**MUST** 发出 **warning 级**诊断（文案含迁移到 `xlsx` 的可复制示例）。
2. **MUST NOT** 仅因 deprecated 而失败。
3. 新 `xlsx` 上再写 `export_xlsx`：**MUST** fail-fast。
4. 移除旧分支 / warning→error：另开 BREAKING。

## Runtime 过渡

- Compile：别名与 `xlsx` → 内部「有 path / 无 path」→ 现有 workbook/sheetbook 实现。
- **本 change 不要求**合并 `resources_workbook` / `resources_sheetbook` 源文件。

## 可维护性与内存（少占优先）

| 阶段 | 动作 | 可维护性 | 内存 |
|---|---|---|---|
| **本 change (c20)** | authoring 别名正规化 + warning | 心智/文档单一 | ≈0（不改驻留模型） |
| **接着** | IR 只保留有 path/无 path | 少一套词 | ≈0 |
| **later** | `refactor-workflow-xlsx-backends-unify` | 对齐/可见性一处改 | 主降复杂度；峰值未必大降 |
| **later** | spill（要 bench） | — | **主杠杆**（plan∑segments） |
| **最后** | 删别名解析 | 代码面最小 | ≈0 |

峰值仍大致：`demand ROWS（可早释）+ plan∑segments + openpyxl 窗`。  
**禁止**默认边写 openpyxl 换峰值（破坏原子 discard）。  
无 path 总线仍占 plan RAM（`book_sheet_rows` 需要）；省的是落盘，不是「零内存」。

## Non-goals

- 删除内存总线语义
- budget/write 回流 YAML
- 默认边写 openpyxl
- 本 change 内硬删 `xlsx_file`/`xlsx_memory`
- 本 change 内合并双后端模块 / spill
