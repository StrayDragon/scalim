# P2: scalim Barrel `__init__.py` 填充（每包一批，逐包验证）

> **来源方案**：
> - `source_plans/3_re-export_chain_audit.plan.md` — 决策 4（events/hooks/workflow barrel 设计，采纳方案 B：Selective barrel）
> - `source_plans/4_package-encapsulation-refactor.plan.md` — 跨方案通用 barrel `__init__.py` 模板（events/hooks 具体代码示例）
> - `source_plans/1_api_surface_governance.plan.md` — 决策点 4（sinks facade，采纳方案 A：第六个官方入口）

## 项目约束

- Python 3.6 兼容；`src/scalim/` 内使用相对导入
- 格式化：ruff（4-space indent, line length 140, double quotes）
- `if TYPE_CHECKING:` 仅用于 type-only imports/aliases
- 质量门禁：`just qa` 必须在每包改动后通过
- 测试覆盖率目标 100%，不得降低现有覆盖率

## 核心原则

1. **先填充 barrel，不移动文件** — 本 Prompt 只在 `__init__.py` 中添加 re-export
2. **新旧路径共存** — 用户仍可 `from scalim.{pkg}.{mod} import X`，同时新增 `from scalim.{pkg} import X`
3. **不破坏类型检查** — re-export 使用显式 import，不用 `import *`
4. **每个包独立验证** — 完成后立即 `just qa`

## 前置条件

- P1 已完成（所有模块已有 `__all__`）

## 前置检查

在修改前，先运行并记录基线：

```bash
just qa  # 记录当前状态
python -c "from scalim.{pkg} import __all__; print(__all__)" 2>/dev/null || echo "无 __all__"
```

---

## 包 1: `sinks/`

### 操作

1. **读取所有子模块的 `__all__`**：对 `sink_base.py`, `sink_csv.py`, `sink_excel.py`, `sink_memory.py`, `sink_pandas.py`, `sink_rows.py` 读取每个文件的 `__all__`，汇总所有公开符号。

2. **填充 `sinks/__init__.py`**：

```python
"""Sink 接口与实现."""
from .sink_base import (
    BaseSink,
    BaseRowSink,
    BaseColumnSink,
    IRowSink,
    IColumnSink,
    ISink,
)
from .sink_csv import (
    CSVSink,
    ColumnCSVSink,
    BlockColumnCSVSink,
    InMemoryCsv,
    InMemoryCsvSink,
)
# ... 其余子模块同理，从各子模块 __all__ 中获取完整列表

__all__ = [
    # 按子模块分组列出，与上面 import 顺序一致
]
```

> **注意**：以上符号列表仅为示例，需根据各子模块实际 `__all__` 内容确定。

3. **类型检查兼容性验证**：

```bash
python -c "
from scalim.sinks import BaseSink, CSVSink
print('runtime import OK')
"
```

4. **确保不与 `TYPE_CHECKING` 冲突**：
   - barrel 中的 import 必须是**无条件的运行时 import**
   - 不得在 barrel `__init__.py` 中使用 `if TYPE_CHECKING:`
   - 如果某个子模块的符号只在 `TYPE_CHECKING` 下存在，则不 re-export

5. **运行门禁**：`just qa`

---

## 包 2: `events/`

### 操作

1. 读取 `event.py`, `events.py`, `catalog.py`, `attribution.py` 的 `__all__`
2. 填充 `events/__init__.py` 为 **selective barrel**（重导出核心符号）：
   - `Event`, `now_ts`, `generate_run_id`
   - 所有 `*Event` dataclass（约 28 个）
   - `EVENT_*` 常量（约 27 个）
   - `EventDescriptor`, `get_event_catalog`, `get_event_catalog_map`
   - `WORKFLOW_*_META_KEY` 常量
3. 验证 + `just qa`

---

## 包 3: `hooks/`

### 操作

1. 读取 `base.py`, `dispatch.py` 的 `__all__`
2. 填充 `hooks/__init__.py`：

```python
"""钩子接口与调度策略."""
from .base import IExecutionHook, BaseHook, HookManager
from .dispatch import HookDispatchStrategy

__all__ = ("IExecutionHook", "BaseHook", "HookManager", "HookDispatchStrategy")
```

3. 验证 + `just qa`

---

## 完成标准（每包）

- `just qa` 通过
- `from scalim.{pkg} import X` 对所有公开符号均可用
- `from scalim.{pkg}.{submod} import X` 旧路径仍然可用
- `git diff` 确认只修改了 `{pkg}/__init__.py`
- 无测试文件被修改
