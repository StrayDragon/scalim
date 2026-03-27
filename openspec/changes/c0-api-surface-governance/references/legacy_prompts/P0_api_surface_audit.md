# P0: scalim 公开 API 表面审计报告（只读分析，不修改任何文件）

> **来源方案**：
> - `source_plans/1_api_surface_governance.plan.md` — 审计数据摘要（274 文件、34 泄漏模块、5 个 `_` 前缀 `__all__` 问题）
> - `source_plans/3_re-export_chain_audit.plan.md` — 数据基底（barrel 现状、外部引用频次）
> - `source_plans/4_package-encapsulation-refactor.plan.md` — 泄漏清单与公开/内部分类矩阵
> - `source_plans/6_api_compatibility_strategy.plan.md` — TYPE_CHECKING 审计维度

## 项目约束

- 代码位于 `src/scalim/`，Python 3.6 运行时兼容
- 质量门禁：`just qa`（lint + test + drift-check + openspec-check）
- 格式化：ruff（4-space indent, line length 140, double quotes）
- `src/scalim/` 内部使用相对导入
- `if TYPE_CHECKING:` 仅用于类型导入/别名，不得用于 fake class interface

## 分析要求

请生成一份结构化的 API 表面审计报告，包含以下部分：

### 1. `__all__` 覆盖率矩阵

扫描 `src/scalim/` 下所有 `.py` 文件，输出如下表格：

| 文件路径 | 有 `__all__` | `__all__` 符号数 | 模块级公开符号数 | 差异 | 分类建议 |

分类建议 = Stable / Provisional / Internal，依据：

- 已被 5 大 facade `__init__.py` re-export 的 → Stable
- 有 `__all__` 但未被 facade re-export 的 → Provisional
- 无 `__all__` 且在 `_internal/` 或 `_` 前缀模块中 → Internal
- 无 `__all__` 且不在 `_internal/` 中 → ⚠ 泄漏，需治理

### 2. `__all__` 合规性检查

列出所有 `__all__` 中包含 `_` 前缀符号的模块，及具体符号名。

### 3. Barrel 入口现状

对每个 `__init__.py`，统计：

- 是否有 re-export（`from .xxx import`）
- re-export 了多少符号
- 是否有 `__all__`
- `__all__` 与实际 re-export 是否一致

### 4. 外部引用路径统计

扫描 `tests/`、`notebooks/`、`packages/` 目录下所有 Python 文件，统计 `from scalim.xxx import` 的所有唯一导入路径，按频次排序。

标注哪些路径指向：

- `[OK]` 官方 facade 入口
- `[OK]` 有 `__all__` 的公开模块
- `[WARN]` 无 `__all__` 的模块（泄漏路径）
- `[BAD]` `_internal/` 或 `_` 前缀模块（不应被外部引用）

### 5. `TYPE_CHECKING` 使用审计

列出所有使用 `if TYPE_CHECKING:` 的文件，检查：

- 是否仅用于 type-only imports/aliases ✓
- 是否包含条件方法定义/ellipsis stubs ✗（违反项目规则）

### 6. 类型导出链路完整性

对于 `typedefs.py` 中的每个类型别名，追踪：

- 是否被某个 `__init__.py` re-export
- 被哪些外部文件直接导入
- 类型检查器（mypy/pyright）是否能通过 re-export 链路正确解析

## 输出格式

请将报告输出为一个 Markdown 文件，保存到 `.tmp/api-surface-audit-report.md`。**不要修改任何源代码文件。**

## 验证

完成后运行 `just qa` 确认分析过程没有意外修改任何文件。
