# Design — remove-deprecated-xlsx-file-memory-kinds

## 目标终态

```text
YAML authoring（唯一）
  xlsx: {}              → pathless（内存总线 / sheetbook 后端）
  xlsx: {path: P}       → pathful（版本化落盘 / workbook 后端）

YAML 拒绝
  xlsx_file / xlsx_memory / memory.export_xlsx
  books.*.kind（flat discriminator，既有）
  observability.*（本 change 起 fail-fast）

Python shortcut（保留调用面）
  RunOverrides.xlsx_file_single_sheet(...)  → 内部构造 pathful book（等价 xlsx.path）
  其它既有 RunOverrides 工厂同理：名字稳定，内部不依赖 deprecated YAML 分支解析
```

## 分层决策

| 层 | 决策 | 兼容性 |
|---|---|---|
| YAML books 别名 | **硬删** | BREAKING |
| IR/runtime `kind` wire shim | **删除对外契约**；身份只认 pathful/pathless | BREAKING（依赖 `get_book_kind`/`options.kind` 字符串的代码） |
| `RunOverrides.xlsx_file_single_sheet` | **保留函数名与签名**；内部改 pathful | 可兼容 |
| YAML `observability.*` | warning+strip → **fail-fast** | BREAKING（原先可跑+warning） |
| `RowId*` | **移除公开别名** | BREAKING（低面：仓内外几乎未直接 import） |

## Kind shim 终态（第 2 项）

当前过渡：

- parse 后 `BookConfig.kind` 仍填 `xlsx_file`/`xlsx_memory`
- compile 写 IR `options.kind` via `legacy_kind_shim`
- `WorkflowResourceManager.get_book_kind` 返回同样字符串

终态：

1. 身份查询只通过 **path 有无** / defs 成员关系（workbook_defs vs sheetbook_defs）
2. 写节点与 materialize **MUST NOT** 再分支在 `"xlsx_file"` / `"xlsx_memory"` 字符串上作为业务 SSOT
3. 若短期内部仍暂存历史字段，MUST NOT 出现在公开契约、文档或测试推荐断言中；本 change 目标是删掉可观测 shim

不合并 `resources_workbook.py` / `resources_sheetbook.py`（另开 refactor）。

## 保留工厂的实现约束

```python
# 调用面不变（示例）
RunOverrides.xlsx_file_single_sheet(
    output_root="./out",
    fields=["a", "b"],
    sheet="detail",
)

# 内部 MUST 等价于 pathful identity（概念）
# books[book_id] ≈ xlsx: {path: output_root, allow_formulas: ...}
# MUST NOT 再依赖 YAML deprecated 分支解析路径
```

可选（非必须）：新增更贴名的 `xlsx_single_sheet` 作为别名工厂；**不得**删除或改名现有 `xlsx_file_single_sheet`。

`BookResourceOverride.kind`：若仍存在，仅作内部/历史字段处理；对外文档与新测试以 path / pathful 为准。工厂实现可继续填充必要字段，但 compile 路径不得要求调用方传入 `"xlsx_file"` 才能工作。

## Observability

- 旧合约 r363：迁移期 warning + ignore
- 新合约：出现已知 `observability.*` → **fail-fast** + 指向 Python/CLI entrypoints
- 未知字段规则不变（不得一律当 observability 处理）

## RowId* 清理

- `BusinessKey` / `RecordKey*` 为 SSOT
- 删除 `RowId` / `RowIdSeq` / `RowIdList`
- `LoaderResult` 等改为 `BusinessKey` 键类型
- 仓内引用一并改完；不提供 runtime DeprecationWarning（typing 别名无法可靠 warn）

## 迁移证据（实施前门禁）

1. 仓库内推荐 YAML / notebooks / skills 示例无 `xlsx_file`/`xlsx_memory` authoring
2. 工厂回归：`xlsx_file_single_sheet` 行为与 `xlsx.path` 声明对拍
3. 旧 YAML 夹具：Before 应失败；After 用 `xlsx` 成功

## 明确不做

- 不删 pathless 内存总线语义
- 不合并 workbook/sheetbook 模块
- write/budget 不回流 YAML
- 不重命名 `xlsx_file_single_sheet`
