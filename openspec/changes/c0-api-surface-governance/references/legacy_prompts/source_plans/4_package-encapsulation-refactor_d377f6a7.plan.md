---
name: package-encapsulation-refactor
overview: "针对 scalim 包结构封装问题，提出三套完整的重构方案（A: 下划线前缀、B: _internal 子目录、C: 混合策略），含目录对比图、影响面分析与迁移路径。"
todos:
  - id: phase0-barrels
    content: "Phase 0: 为 sinks/, events/, hooks/, spec/ 填充 barrel __init__.py（仅新增重导出，零破坏）"
    status: pending
  - id: phase1-sinks
    content: "Phase 1a: sinks/ 重构 — 建 _internal/ 子目录，移入文件并去 sink_ 前缀"
    status: pending
  - id: phase1-events
    content: "Phase 1b: events/ 重构 — 子模块加 _ 前缀"
    status: pending
  - id: phase1-hooks
    content: "Phase 1c: hooks/ 重构 — base.py/dispatch.py 加 _ 前缀，填充 barrel"
    status: pending
  - id: phase1-utils
    content: "Phase 1d: utils/ 移入 _internal/utils/，消除公开命名空间"
    status: pending
  - id: phase1-typedefs-warningsx
    content: "Phase 1e: warningsx.py 移入 _internal/，typedefs 核心类型从顶层重导出"
    status: pending
  - id: phase2-external
    content: "Phase 2: 全量修改 tests/notebooks/packages 的外部导入路径"
    status: pending
  - id: phase3-cleanup
    content: "Phase 3: 移除兼容 shim（如有）+ ruff 检查 + 运行 just qa"
    status: pending
isProject: false
---

# scalim 包结构封装重构方案

## 现状诊断

265 个 Python 文件（不含 vendor），已有 `_internal/` 模式分布在 `hooks/`、`ob/`、`execution/` 等多处，但 `sinks/`、`utils/`、`events/`、`spec/` 的 `__init__.py` 全是空壳——有文件无导出。

### 泄露清单（按严重度排序）

- **sinks/** — 6 个 `sink_*.py` 直接可达，外部引用 30+ 处（tests + notebooks + packages）
  - 用户路径示例：`from scalim.sinks.sink_memory import InMemoryRowSink`
- **events/** — `__init__.py` docstring 明确要求用户深入子模块，外部引用 20+ 处
  - 用户路径示例：`from scalim.events.events import PipelineStartEvent`（events.events 丑陋重复）
- **hooks/** — `base.py` 包含全部公开接口，外部引用 10+ 处
  - 用户路径示例：`from scalim.hooks.base import BaseHook`
- **typedefs.py** — 顶层裸模块，框架级公开类型，外部引用 8+ 处
- **warningsx.py** — 顶层裸模块，仅 1 个类
- **utils/** — 纯内部工具，但被 `packages/scalim-misc` 直接引用了 `converters`

### 公开 vs 内部分类


| 模块           | 公开符号                                                                                                                                                                                                                                                                                                                                | 内部符号                                                                                                                                           |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| sinks/       | `BaseSink`, `BaseRowSink`, `IRowSink`, `IColumnSink`, `CSVSink`, `ColumnCSVSink`, `BlockColumnCSVSink`, `InMemoryCsvSink`, `InMemoryCsv`, `ExcelSink`, `ColumnExcelSink`, `ExcelWorkbookSink`, `InMemoryRowSink`, `InMemoryColumnSink`, `InMemoryListSink`, `PandasRowSink`, `PandasColumnSink`, `InMemoryRows`, `InMemoryRowsSink` | `create_temp_path`, `update_column`, `update_columns`, `store_rows_as_columns`, `iter_row_values`, `ColumnData`, `ColumnValues`, `ColumnBatch` |
| events/      | `Event`, 所有 `*Event` dataclass, `EVENT_`* 常量, `EventDescriptor`, `get_event_catalog`, `WORKFLOW_*_META_KEY`                                                                                                                                                                                                                         | `_EVENT_CATALOG` 列表本身                                                                                                                          |
| hooks/       | `IExecutionHook`, `BaseHook`, `HookManager`, `HookDispatchStrategy`                                                                                                                                                                                                                                                                 | `_internal/manager_*` 全部                                                                                                                       |
| typedefs.py  | `FieldValue`, `RowData`, `LoaderResult`, `ParallelMode`, `SourceSpecIrCacheMode` 等全部                                                                                                                                                                                                                                                | 无                                                                                                                                              |
| warningsx.py | `ScalimExperimentalWarning`                                                                                                                                                                                                                                                                                                         | 无                                                                                                                                              |
| utils/       | `must_get_seps_values_first_int`, `auto_str_normalize`（被 scalim-misc 用了）                                                                                                                                                                                                                                                            | `graph`, `excel`, `iterables`, `json_like`, `relation_diagnostics`, `relation_signature` 大部分                                                   |


---

## 方案 A：下划线前缀（`_module.py`）

### 设计思路

对所有内部实现模块加 `_` 前缀，`__init__.py` 作为唯一公开入口重导出。

### 目录结构（重构后）

```
src/scalim/
├── __init__.py                    # 不变
├── _project_constants.py          # 已有 _
├── _typedefs.py                   # ← 重命名 (内容不变，从 __init__ 或 sinks/__init__ 重导出)
├── _warningsx.py                  # ← 重命名
│
├── sinks/
│   ├── __init__.py                # ← 填充 barrel: 重导出所有公开类
│   ├── _sink_base.py              # ← 加 _
│   ├── _sink_csv.py               # ← 加 _
│   ├── _sink_excel.py             # ← 加 _
│   ├── _sink_memory.py            # ← 加 _
│   ├── _sink_pandas.py            # ← 加 _
│   └── _sink_rows.py              # ← 加 _
│
├── events/
│   ├── __init__.py                # ← 填充 barrel: 重导出 Event, *Event, EVENT_*, ...
│   ├── _event.py                  # ← 加 _
│   ├── _events.py                 # ← 加 _
│   ├── _catalog.py                # ← 加 _
│   └── _attribution.py            # ← 加 _
│
├── hooks/
│   ├── __init__.py                # ← 填充 barrel: 重导出 IExecutionHook, BaseHook, HookManager
│   ├── _base.py                   # ← 加 _
│   ├── _dispatch.py               # ← 加 _
│   └── _internal/                 # 不变
│
├── utils/
│   ├── __init__.py                # ← 填充 barrel: 仅导出需公开的极少数符号
│   ├── _converters.py             # ← 加 _
│   ├── _excel.py                  # ← 加 _
│   ├── _graph.py                  # ← 加 _
│   ├── _iterables.py              # ← 加 _
│   ├── _json_like.py              # ← 加 _
│   ├── _relation_diagnostics.py   # ← 加 _
│   └── _relation_signature.py     # ← 加 _
│
├── spec/
│   ├── __init__.py                # ← 填充: from .ir import * 或选择性导出
│   └── ir/                        # 不变 (已有良好 barrel)
```

### 优势

- **最小结构变动** — 文件仍在原目录，只加了 `_` 前缀
- **git diff 可追踪** — `git mv` 保留文件历史
- **IDE 导航友好** — 文件名一眼区分公开/内部
- **与现有 `_project_constants.py` 模式一致**
- **搜索友好** — `_sink_csv.py` 搜 `sink_csv` 仍能命中

### 劣势

- `**_` 前缀只是"软约定"** — Python 不强制阻止 `import scalim.sinks._sink_csv`
- **大量文件重命名** — 约 20 个文件 rename，所有内部相对导入全部要改
- **sinks 目录仍暴露实现分类** — `_sink_csv.py`、`_sink_excel.py` 文件名仍泄露后端类型
- **不够 DRY** — `__init__.py` barrel 和模块里的 `__all__` 形成两层导出声明

### 影响面估算

- 重命名文件：~20 个
- 修改内部相对导入：~40 处（sinks 内部互引 + 其他包引 sinks/utils/events）
- 修改外部导入（tests/notebooks/packages）：~60 处
- 总涉及文件：~50 个

---

## 方案 B：_internal 子目录

### 设计思路

所有实现文件移入 `_internal/` 子目录，`__init__.py` 作为唯一公开入口。与 `hooks/_internal/`、`ob/_internal/` 现有模式完全一致。

### 目录结构（重构后）

```
src/scalim/
├── __init__.py                       # 不变
├── _project_constants.py             # 不变
├── _internal/
│   ├── __init__.py                   # 已有
│   ├── loggingx.py                   # 已有
│   ├── typedefs.py                   # ← 从顶层移入
│   └── warningsx.py                  # ← 从顶层移入
│
├── sinks/
│   ├── __init__.py                   # ← 填充 barrel
│   └── _internal/
│       ├── __init__.py               # 新建
│       ├── base.py                   # ← sink_base.py 移入 + 去 sink_ 前缀
│       ├── csv.py                    # ← sink_csv.py 移入
│       ├── excel.py                  # ← sink_excel.py 移入
│       ├── memory.py                 # ← sink_memory.py 移入
│       ├── pandas.py                 # ← sink_pandas.py 移入
│       └── rows.py                   # ← sink_rows.py 移入
│
├── events/
│   ├── __init__.py                   # ← 填充 barrel
│   └── _internal/
│       ├── __init__.py               # 新建
│       ├── event.py                  # ← 移入
│       ├── events.py                 # ← 移入
│       ├── catalog.py                # ← 移入
│       └── attribution.py            # ← 移入
│
├── hooks/
│   ├── __init__.py                   # ← 填充 barrel
│   ├── _internal/                    # 已有，不变
│   │   ├── manager_base.py
│   │   ├── manager_events.py
│   │   ├── ...
│   │   ├── base.py                   # ← base.py 移入
│   │   └── dispatch.py               # ← dispatch.py 移入
│
├── utils/
│   ├── __init__.py                   # ← 填充 barrel (几乎不导出)
│   └── _internal/
│       ├── __init__.py
│       ├── converters.py
│       ├── excel.py
│       ├── graph.py
│       ├── iterables.py
│       ├── json_like.py
│       ├── relation_diagnostics.py
│       └── relation_signature.py
│
├── spec/
│   ├── __init__.py                   # ← 填充: 转发到 ir/
│   └── ir/                           # 不变
```

### 优势

- **最强封装信号** — `_internal` 是 Python 社区公认的"不要碰"标志，比 `_` 前缀更明确
- **与代码库已有模式 100% 一致** — `hooks/_internal/`、`ob/_internal/`、`execution/*/_internal/` 已有 12 个 `_internal/` 目录
- **顺带解决命名泄露** — `sink_csv.py` 移入后可改名为 `csv.py`，文件名不再暴露
- **目录结构干净** — 用户看到 `sinks/` 只有 `__init__.py`，零噪音
- **便于 linter 规则** — 可以用 ruff 的 `banned-module-level-imports` 或自定义检查禁止 `_internal` 导入

### 劣势

- **文件移动路径更长** — `git mv` 路径较深，review diff 时上下文更难看
- **增加嵌套深度** — `scalim/sinks/_internal/csv.py` 比 `scalim/sinks/sink_csv.py` 多一层
- **内部相对导入变更更大** — 从 `from .sink_base import` 变为 `from ._internal.base import` 或 `from .base import`（同一 `_internal/` 内）
- **对小包不经济** — `events/` 只有 4 个文件就建一个 `_internal/` 有点重
- **hooks/ 合并问题** — `base.py` 移入已有的 `_internal/` 后，和 `manager_`* 混在一起，逻辑分组不够清晰

### 影响面估算

- 移动文件：~20 个
- 新建 `_internal/__init__.py`：~4 个
- 修改内部相对导入：~50 处
- 修改外部导入（tests/notebooks/packages）：~60 处
- 总涉及文件：~55 个

---

## 方案 C：混合策略（推荐）

### 设计思路

根据每个包的**规模和性质**选择最适合的封装手段，而不是一刀切：

- **大目录（sinks/）** → `_internal/` 子目录（文件多，且需要重命名去掉 `sink_` 前缀）
- **中等目录（events/、hooks/）** → barrel 重导出 + 内部模块加 `_` 前缀
- **纯内部工具（utils/）** → 整个包降级为 `_utils/`（或移入 `_internal/`）
- **小文件（typedefs.py、warningsx.py）** → 移入 `_internal/` 或合并到相关包

### 目录结构（重构后）

```
src/scalim/
├── __init__.py                         # ← 扩展: 重导出 typedefs 中的公开类型
├── _project_constants.py               # 不变
├── _internal/
│   ├── __init__.py                     # 已有
│   ├── loggingx.py                     # 已有
│   ├── warningsx.py                    # ← 从顶层移入 (仅 1 个类)
│   └── utils/                          # ← 整个 utils/ 移入 (纯内部工具)
│       ├── __init__.py
│       ├── converters.py
│       ├── excel.py
│       ├── graph.py
│       ├── iterables.py
│       ├── json_like.py
│       ├── relation_diagnostics.py
│       └── relation_signature.py
│
├── typedefs.py                         # ← 保留原位 (框架级公开类型)
│                                       #    但也从 scalim.__init__ 重导出核心类型
│
├── sinks/                              # ← _internal 模式 (文件多 + 需重命名)
│   ├── __init__.py                     # ← 填充 barrel: 所有公开 Sink 类
│   └── _internal/
│       ├── __init__.py
│       ├── base.py
│       ├── csv.py
│       ├── excel.py
│       ├── memory.py
│       ├── pandas.py
│       └── rows.py
│
├── events/                             # ← _ 前缀模式 (文件少 + 已有 _internal 先例少)
│   ├── __init__.py                     # ← 填充 barrel: Event, *Event, EVENT_*, ...
│   ├── _event.py
│   ├── _events.py
│   ├── _catalog.py
│   └── _attribution.py
│
├── hooks/                              # ← barrel 模式 (已有 _internal，只需填充 __init__)
│   ├── __init__.py                     # ← 填充 barrel: IExecutionHook, BaseHook, HookManager
│   ├── _base.py                        # ← 加 _ (不移入 _internal，避免与 manager_* 混杂)
│   ├── _dispatch.py                    # ← 加 _
│   └── _internal/                      # 不变
│
├── spec/
│   ├── __init__.py                     # ← 填充: 转发到 ir/ 的 barrel
│   └── ir/                             # 不变
│
├── ob/                                 # 不变 (已有良好封装)
├── execution/                          # 不变
├── planning/                           # 不变
└── ...
```

### 每个包的策略及理由

**sinks/ → `_internal/`**

- 理由：6 个文件，且 `sink_` 前缀需要在重命名时一并清理
- 好处：用户看到 `from scalim.sinks import InMemoryRowSink`，不再暴露后端分类
- barrel 示例：

```python
# sinks/__init__.py
from ._internal.base import BaseSink, BaseRowSink, BaseColumnSink, IRowSink, IColumnSink, ISink
from ._internal.csv import CSVSink, ColumnCSVSink, BlockColumnCSVSink, InMemoryCsv, InMemoryCsvSink
from ._internal.excel import ExcelSink, ColumnExcelSink, ExcelWorkbookSink
from ._internal.memory import InMemoryRowSink, InMemoryColumnSink, InMemoryListSink
from ._internal.pandas import PandasRowSink, PandasColumnSink
from ._internal.rows import InMemoryRows, InMemoryRowsSink

__all__ = (
    "BaseSink", "BaseRowSink", "BaseColumnSink",
    "IRowSink", "IColumnSink", "ISink",
    "CSVSink", "ColumnCSVSink", "BlockColumnCSVSink",
    "InMemoryCsv", "InMemoryCsvSink",
    "ExcelSink", "ColumnExcelSink", "ExcelWorkbookSink",
    "InMemoryRowSink", "InMemoryColumnSink", "InMemoryListSink",
    "PandasRowSink", "PandasColumnSink",
    "InMemoryRows", "InMemoryRowsSink",
)
```

**events/ → `_` 前缀**

- 理由：只有 4 个文件，建 `_internal/` 目录太重
- `__init__.py` 重导出全部公开符号，用户路径缩短：
  - Before: `from scalim.events.events import PipelineStartEvent`
  - After: `from scalim.events import PipelineStartEvent`

**hooks/ → 仅填充 barrel**

- 理由：`_internal/` 已有且分工明确（manager 拆分），`base.py` 和 `dispatch.py` 只需加 `_` 即可
- `__init__.py` 重导出核心接口

**utils/ → 整体移入 `_internal/utils/`**

- 理由：这是纯内部工具包，不应出现在 `scalim.utils` 的公开命名空间
- `packages/scalim-misc` 用了 `converters.must_get_seps_values_first_int`，但这属于 misc 的内部使用，可以直接改导入路径
- 如果确实有少量 util 要公开，在 `scalim._internal.utils.__init__` 里标注，并从更合适的公开入口重导出

**typedefs.py → 保留原位 + 从 `scalim.__init__` 重导出核心类型**

- 理由：`FieldValue`、`RowData`、`LoaderResult` 是用户写 loader 时的高频类型
- `scalim.typedefs` 路径已被外部使用，保留作为稳定路径
- 但同时从 `scalim` 顶层重导出最核心的几个（`RowData`、`FieldValue`、`LoaderResult`）

**warningsx.py → 移入 `_internal/`**

- 理由：只有 1 个类，不值得占顶层位置
- 从 `scalim.__init__` 重导出 `ScalimExperimentalWarning`

### 优势

- **因地制宜** — 每个包用最合适的策略，避免过度工程或不够封装
- **最大限度复用已有模式** — `_internal/` 模式已在 `hooks/`、`ob/`、`execution/` 中验证
- **用户体验最优** — 用户永远只需 `from scalim.sinks import X`、`from scalim.events import Y`
- **渐进实施** — 可以按包分阶段执行，每个包独立一个 PR
- `**utils/` 彻底内部化** — 消除了"用户该不该用 utils"的歧义

### 劣势

- **规则不统一** — 三种策略混用，需要文档说明"何时用哪种"
- **新贡献者学习成本** — 需要理解封装策略选择的理由
- **总工作量最大** — 综合了 A 和 B 的改动

### 影响面估算

- 移动/重命名文件：~22 个
- 新建 `_internal/__init__.py`：~2 个（sinks, _internal/utils）
- 修改内部相对导入：~55 处
- 修改外部导入（tests/notebooks/packages）：~60 处
- 总涉及文件：~60 个

---

## 三方案对比总结


| 维度       | 方案 A: `_` 前缀       | 方案 B: `_internal/` | 方案 C: 混合                |
| -------- | ------------------ | ------------------ | ----------------------- |
| 封装强度     | 中（软约定）             | 强（社区公认）            | 强（分层施策）                 |
| 结构一致性    | 高（单一规则）            | 高（单一规则）            | 中（需文档）                  |
| 与现有模式兼容  | 部分                 | 完全                 | 完全                      |
| 命名泄露修复   | 否（`_sink_csv` 仍泄露） | 是（`csv.py`）        | 是（sinks 用 `_internal/`） |
| 嵌套增加     | 无                  | 1 层                | 视包而定                    |
| 工作量      | 小                  | 中                  | 中偏大                     |
| 渐进实施     | 容易                 | 容易                 | 最容易（天然分包）               |
| 用户体验提升   | 有（barrel）          | 有（barrel）          | 最优（barrel + 顶层重导出）      |
| git 历史保留 | `git mv` 可追踪       | `git mv` 可追踪       | `git mv` 可追踪            |


---

## 跨方案通用：barrel `__init__.py` 模板

无论选哪种方案，以下 barrel 结构是通用的：

### events/**init**.py

```python
"""事件类型、事件目录与辅助工具."""
from ._event import Event                          # 或 ._internal.event
from ._events import (                             # 或 ._internal.events
    BatchEndEvent, BatchStartEvent, ColumnWriteEvent,
    PipelineEndEvent, PipelineStartEvent,
    # ... 所有公开事件 dataclass
)
from ._catalog import (                            # 或 ._internal.catalog
    EVENT_PIPELINE_START, EVENT_PIPELINE_END,
    EventDescriptor, get_event_catalog, get_event_catalog_map,
    # ... 所有 EVENT_* 常量
)
from ._attribution import (                        # 或 ._internal.attribution
    WORKFLOW_EXEC_ID_META_KEY, WORKFLOW_NODE_ID_META_KEY,
    WORKFLOW_ATTRIBUTION_META_KEYS,
)

__all__ = (...)
```

### hooks/**init**.py

```python
"""钩子接口与实现."""
from ._base import IExecutionHook, BaseHook, HookManager
from ._dispatch import HookDispatchStrategy

__all__ = ("IExecutionHook", "BaseHook", "HookManager", "HookDispatchStrategy")
```

---

## 迁移路径（适用于任一方案）

1. **Phase 0: 建 barrel（无破坏性）** — 先在现有 `__init__.py` 中填充重导出，新旧路径同时可用
2. **Phase 1: 移动/重命名文件** — `git mv` + 修改所有内部相对导入
3. **Phase 2: 修改外部导入** — tests/notebooks/packages 统一迁移到 barrel 路径
4. **Phase 3: 清理** — 移除兼容 shim（如果有的话）

### 如果需要兼容 shim（用户不在乎破坏性变更则跳过）

```python
# 兼容 shim 示例: scalim/sinks/sink_memory.py (仅过渡期保留)
import warnings
warnings.warn(
    "scalim.sinks.sink_memory is deprecated, import from scalim.sinks instead",
    DeprecationWarning, stacklevel=2,
)
from ._internal.memory import *  # noqa: F401,F403
```

