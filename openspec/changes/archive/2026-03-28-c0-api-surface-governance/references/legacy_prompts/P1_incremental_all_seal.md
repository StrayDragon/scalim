# P1: scalim `__all__` 增量补充（分批执行，每批 ≤10 文件）

> **来源方案**：
> - `source_plans/1_api_surface_governance.plan.md` — 决策点 2（`_` 前缀修复，采纳方案 A：仅从 `__all__` 移除）、决策点 3（34 泄漏模块分类处理）
> - `source_plans/4_package-encapsulation-refactor.plan.md` — 泄漏清单按严重度排序、公开 vs 内部分类表
> - `source_plans/2_typedefs_audit_plans.plan.md` — 共同前提 P1：`typedefs.py` 添加 `__all__`

## 项目约束

- Python 3.6 兼容；`src/scalim/` 内使用相对导入
- 格式化：ruff（4-space indent, line length 140, double quotes）
- `if TYPE_CHECKING:` 仅用于 type-only imports/aliases
- 质量门禁：`just qa` 必须在每批改动后通过
- 测试覆盖率目标 100%，不得降低现有覆盖率

## 核心原则

1. **每批最多修改 10 个文件**，改完立即运行 `just qa`
2. **只做增量**：添加 `__all__`，不移动/重命名/删除任何文件
3. **不改变任何运行时行为**：补 `__all__` 只影响 `from module import *`
4. **不破坏类型检查**：
   - 如果文件中有 `if TYPE_CHECKING:` 块导入的类型被用在 `__all__` 里，那这个类型必须在非 `TYPE_CHECKING` 路径下也可访问（否则不放入 `__all__`）
   - `__all__` 中的符号必须是运行时可导入的，不能只存在于 `TYPE_CHECKING` 分支

## 批次划分建议

根据 P0 审计报告确定具体文件。以下是推荐的分批顺序：

### 批次 1: `_internal/` 下的模块（最安全，全部 `__all__ = []`）

- `hooks/_internal/common.py`
- `hooks/_internal/manager_events.py`
- `hooks/_internal/manager_registry.py`
- `hooks/_internal/manager_state.py`
- `hooks/_internal/manager_subscriptions.py`
- `ob/_internal/common.py`
- `ob/_internal/manager_capture.py`
- `ob/_internal/manager_emit.py`
- `ob/_internal/manager_registry.py`
- `ob/_internal/manager_state.py`

### 批次 2: `execution/` 内部模块

- `execution/executor/batch/_internal/segments.py` → `__all__ = []`
- `execution/executor/batch/_internal/stage_spans.py` → `__all__ = []`
- `execution/executor/runtime/_internal/relation_guardrails.py` → `__all__ = []`
- `execution/executor/operators/_internal/loader_guardrails.py` → `__all__ = []`
- `execution/executor/operators/_internal/sentinels.py` → `__all__ = []`
- `execution/adaptive/_internal/loadref_scheduler_base.py` → `__all__ = []`
- `execution/adaptive/_internal/loadref_scheduler_execution.py` → `__all__ = []`
- `execution/adaptive/_internal/loadref_scheduler_planning.py` → `__all__ = []`
- `execution/adaptive/_internal/loadref_scheduler_support.py` → `__all__ = []`

### 批次 3: CLI / vendor / utils 散模块

- `cli/main.py` → `__all__ = []`
- `cli/yaml_dsl.py` → `__all__ = []`
- `cli/yaml_dsl_lsp.py` → `__all__ = []`
- `utils/converters.py` → `__all__ = []`
- `utils/excel.py` → `__all__ = []`
- `utils/graph.py` → `__all__ = []`
- `utils/json_like.py` → `__all__ = []`
- `vendor/compact/typing_extensionsx.py` → `__all__ = []`
- `vendor/litejinja2/typedefs.py` → `__all__ = []`

### 批次 4: `typedefs.py` + `planning/` 子模块（需列出具体公开符号）

- `typedefs.py` → 补 `__all__`，列出所有公开类型别名（排除 `RowId`/`RowIdSeq`/`RowIdList` 兼容别名和 `DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY`）
- `planning/builder.py` → 补 `__all__`（列出被 `planning/__init__.py` re-export 的符号）
- `planning/metadata.py` → 同上
- `planning/stages.py` → 同上

### 批次 5: `__all__` 中 `_` 前缀符号修复

- `workflow/resources_base.py` → 从 `__all__` 中移除 `_` 前缀条目
- `workflow/resources_csv.py` → 同上
- `workflow/resources_workbook.py` → 同上
- `workflow/resources_sheetbook.py` → 同上
- `dsl/by_yaml/runtime/conversion.py` → 同上

## 每批操作步骤

对每个文件：

1. 读取文件，确认当前无 `__all__`（或需修复的 `__all__`）
2. 确认分类：
   - `_internal/` 目录下 → `__all__ = []`
   - 纯内部工具 → `__all__ = []`
   - 被 facade re-export 的 → `__all__` 列出具体符号
3. 在文件中 import 区域之后、第一个定义之前，添加 `__all__`
4. 用 ruff 格式化修改的文件

## 类型安全检查清单

对每个添加了非空 `__all__` 的文件：

- [ ] `__all__` 中每个符号在模块顶层有定义（`def`/`class`/赋值）
- [ ] 无 `_` 前缀符号在 `__all__` 中（除 `__version__` 等 dunder）
- [ ] 无 `TYPE_CHECKING`-only 的符号在 `__all__` 中
- [ ] 如果符号来自 re-export（`from .xxx import`），确认源模块也有该符号在 `__all__` 中

## 验证

```bash
# 每修改完一个文件后格式化
ruff format <file>

# 每批全部完成后
just qa
```

如果 `just qa` 失败：

1. **不要尝试修改测试来适应你的改动**
2. 回退本批改动，分析失败原因
3. 将失败的文件从本批移出，放入下一批，并报告原因

## 完成标准

- `just qa` 通过
- `git diff --stat` 确认只修改了目标文件
- 无测试文件被修改
