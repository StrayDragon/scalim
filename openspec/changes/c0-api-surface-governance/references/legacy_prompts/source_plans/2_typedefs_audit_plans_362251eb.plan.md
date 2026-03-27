---
name: typedefs audit plans
overview: 针对 scalim 类型定义与公开类型契约审计，给出四个递进方案的完整实施计划与优劣分析，不回避破坏性更改。
todos:
  - id: plan-selection
    content: 用户确认选择哪个方案（A/B/C/D）或提出修改意见
    status: pending
  - id: add-all-typedefs
    content: typedefs.py 添加分层 __all__
    status: pending
  - id: create-types-module
    content: 新建 scalim/types.py 聚合公开类型（如选 B/C/D）
    status: pending
  - id: move-diagnostic-constant
    content: 搬移 DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY 到 load_ref 内部
    status: pending
  - id: export-warning
    content: ScalimExperimentalWarning 从 scalim 根或 types 导出
    status: pending
  - id: deprecate-compat-aliases
    content: 文档级废弃 RowId/RowIdSeq/RowIdList
    status: pending
  - id: update-external-imports
    content: 更新 16 个外部文件的 import 路径
    status: pending
  - id: update-docs
    content: 更新文档推荐入口说明
    status: pending
  - id: qa-validation
    content: just qa 全量验证
    status: pending
isProject: false
---

# scalim 类型定义重组：全方案计划与优劣分析

## 现状量化摘要

- [typedefs.py](src/scalim/typedefs.py): 30 个类型别名 + 1 枚举 + 1 常量，**无 `__all__`**，无官方入口重导出
- 框架内部引用: **52 个文件**通过相对 import 引用 typedefs
- 外部引用: **16 个文件** (tests/notebooks/packages) 通过 `from scalim.typedefs import ...` 引用
- [warningsx.py](src/scalim/warningsx.py): 有 `__all__`，但无入口重导出，仅 1 处内部使用
- [spec/ir/aliases/\_\_init\_\_.py](src/scalim/spec/ir/aliases/__init__.py): 7 个 Callable 类型，**已**从 `scalim.spec.ir` 重导出（做得好的部分）
- 官方入口: `scalim.dsl.by_yaml`, `scalim.spec.ir`, `scalim.planning`, `scalim.execution`, `scalim.ob`

---

## 共同前提操作（所有方案均需）

无论选哪个方案，以下操作都应执行：

### P1. `typedefs.py` 添加 `__all__`

按 Tier 分层声明，提高模块自描述能力。

### P2. `DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY` 搬离 typedefs

移到使用它的位置附近：`src/scalim/execution/executor/operators/load_ref/context.py` 同级或创建 `_messages.py`。测试文件 `tests/test_hooks.py` 需同步更新导入路径。

### P3. 向后兼容别名处理

`RowId`, `RowIdSeq`, `RowIdList`:
- 保留在 typedefs.py 中（不删除）
- 从任何新 `__all__` / 公开入口中**排除**
- docstring 标注 `[Deprecated: use BusinessKey / Sequence[BusinessKey] / List[BusinessKey]]`
- 理由：Python 3.6 下类型别名赋值无法触发 DeprecationWarning，只能做文档级废弃

### P4. `ScalimExperimentalWarning` 导出

从 [scalim/\_\_init\_\_.py](src/scalim/__init__.py) 导出（或从新 `scalim.types` 导出，取决于方案）。

---

## 方案 A：最小侵入 — 仅从现有入口重导出

### 思路

不新建模块，利用已有的 5 个官方入口，按"领域就近"原则重导出类型。

### 改动清单

| 文件 | 操作 |
|------|------|
| `src/scalim/typedefs.py` | 添加 `__all__`（Tier 1-2） |
| `src/scalim/dsl/by_yaml/__init__.py` | 重导出 `ParallelMode`, `KeyNormalizationMode`（出现在 `run()` 签名） |
| `src/scalim/spec/ir/__init__.py` | 重导出 `RowData`, `FieldValue`, `LoaderResult`, `BusinessKey`, `SourceSpecIrCacheMode`, `StaticParams`, `LookupKey`, `RuntimeValue` |
| `src/scalim/ob/__init__.py` | 重导出 `PerformanceReportFormat`, `RelationReportFormat`, `RelationLookupResult` |
| `src/scalim/sinks/sink_base.py` 或新建 `sinks/__init__.py` | 重导出 `SinkRowKey`, `SinkRowKeySeq`, `FieldPresentationKind` |
| `src/scalim/__init__.py` | 重导出 `ScalimExperimentalWarning` |
| `src/scalim/execution/executor/operators/load_ref/_messages.py` (新建) | 搬入 `DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY` |
| `tests/test_hooks.py` | 更新 import 路径 |

### 用户导入体验

```python
from scalim.spec.ir import RowData, FieldValue, LoaderResult
from scalim.dsl.by_yaml import run, ParallelMode
from scalim.ob import PerformanceReportFormat
from scalim import ScalimExperimentalWarning
# 旧路径仍可用
from scalim.typedefs import RowData  # 仍然有效
```

### 优劣分析

**优势**:
- 改动量最小（~8 个文件，纯增量）
- 零 breaking change（旧 import 路径全部保留）
- 不引入新的模块概念
- 符合 `__init__.py` 中已有的"推荐入口"哲学

**劣势**:
- 用户必须知道"RowData 在 spec.ir，ParallelMode 在 dsl.by_yaml"——**类型散落在领域入口中**
- 没有一个"去这里找所有类型"的统一答案
- `FieldPresentationKind` 等类型不明确属于哪个入口（spec.ir? sinks?）
- 如果未来新增类型，要反复决定"放哪个入口"

---

## 方案 B：新建 `scalim.types` 公开模块

### 思路

创建一个新的 `scalim/types.py`，作为**所有公开类型的唯一聚合入口**。`typedefs.py` 保留为内部 SSOT。

### 改动清单

| 文件 | 操作 |
|------|------|
| `src/scalim/types.py` **(新建)** | 从 typedefs + warningsx + spec.ir.aliases 聚合重导出所有公开类型 |
| `src/scalim/typedefs.py` | 添加 `__all__`，docstring 更新为"内部 SSOT，公开入口为 `scalim.types`" |
| `src/scalim/__init__.py` | docstring 中添加 `scalim.types` 为推荐入口 |
| `src/scalim/execution/executor/operators/load_ref/_messages.py` (新建) | 搬入常量 |
| 16 个外部文件 (tests/notebooks/packages) | **可选**: 将 `from scalim.typedefs import` 改为 `from scalim.types import` |
| `tests/test_hooks.py` | 更新常量 import 路径 |

### `scalim/types.py` 内容设计

```python
"""scalim 公开类型入口.

所有用户可见的类型别名、Literal 类型、枚举、Warning 均从此处导出.
"""

# --- 数据类型 ---
from .typedefs import (
    BusinessKey,
    FieldValue,
    LoaderResult,
    LookupKey,
    RecordKey,
    RecordKeySeq,
    RowData,
    RuntimeValue,
    SinkRowKey,
    SinkRowKeySeq,
    SourceSpecIrCacheMode,
    StaticParams,
)

# --- Literal 类型 ---
from .typedefs import (
    FieldPresentationKind,
    KeyNormalizationMode,
    ParallelMode,
    PerformanceReportFormat,
    RelationLookupResult,
    RelationReportFormat,
)

# --- Callable 类型 (来自 spec.ir.aliases) ---
from .spec.ir.aliases import (
    LoaderExtractor,
    LoaderParamsBuilder,
    LoaderResultMapCallable,
    LookupKeyCast,
    LookupKeySpec,
    MainSourceRowIterableCallable,
    NormalizedLookupKeySpec,
)

# --- Warning ---
from .warningsx import ScalimExperimentalWarning

__all__ = [...]  # 完整列表
```

### 用户导入体验

```python
from scalim.types import RowData, FieldValue, ParallelMode
from scalim.types import LoaderResultMapCallable
from scalim.types import ScalimExperimentalWarning
# 旧路径仍可用 (但文档不再推荐)
from scalim.typedefs import RowData
```

### 优劣分析

**优势**:
- 用户有一个**唯一的、可发现的**类型入口（`scalim.types`）
- `scalim.types` 是 Python 社区惯例（如 `mypy.types`, `pydantic.types`）
- 未来新增类型只需在 types.py 添加一行，不需要反复决定归属
- Callable 类型和数据类型终于可以从同一个地方导入
- 内部仍从 `typedefs.py` 相对导入，不影响 52 个内部文件

**劣势**:
- 新增一个模块（`types.py`），增加概念负担
- 与 Python stdlib `types` 模块同名，`from scalim.types import ...` 没有歧义，但 `import scalim.types` 后变量名 shadow 了 `types`
- `typedefs.py` 变成了"半废弃"状态（不删除但不推荐），需要文档管理
- 各官方入口（spec.ir, dsl.by_yaml 等）仍不直接提供类型，需要跳到 `scalim.types`

---

## 方案 C：组合方案（A + B）— 多入口聚合

### 思路

同时做两件事：`scalim.types` 作为类型总入口 + 各官方入口也重导出领域相关类型。用户可以选择最舒适的路径。

### 改动清单

方案 A + 方案 B 的合集。具体为：

| 文件 | 操作 |
|------|------|
| `src/scalim/types.py` **(新建)** | 全量公开类型聚合 |
| `src/scalim/typedefs.py` | 添加 `__all__` |
| `src/scalim/dsl/by_yaml/__init__.py` | 重导出 `ParallelMode`, `KeyNormalizationMode` |
| `src/scalim/spec/ir/__init__.py` | 重导出 `RowData`, `FieldValue`, `LoaderResult` 等 |
| `src/scalim/ob/__init__.py` | 重导出报告格式类型 |
| `src/scalim/__init__.py` | 重导出 `ScalimExperimentalWarning`；docstring 添加 `scalim.types` |
| 常量搬移 + 测试更新 | 同上 |
| 16 个外部文件 | **可选**: 迁移到新路径 |

### 用户导入体验

```python
# 路径 1: 统一入口（推荐给不确定的用户）
from scalim.types import RowData, ParallelMode

# 路径 2: 领域入口（推荐给了解架构的用户）
from scalim.spec.ir import RowData
from scalim.dsl.by_yaml import run, ParallelMode

# 路径 3: 旧路径（向后兼容）
from scalim.typedefs import RowData
```

### 优劣分析

**优势**:
- **最大灵活性**: 用户可以按偏好选择导入路径
- `scalim.types` 做"不知道在哪就去这里找"的兜底
- 领域入口做"和 API 一起用更自然"的就近导出
- 各路径之间是相同对象的别名引用（`is` 相等），不增加运行时开销
- 向后完全兼容

**劣势**:
- **改动量最大**（~12+ 文件）
- **同一个类型有 3 个合法导入路径**，可能导致代码风格不一致（同一项目里有人用 `scalim.types`，有人用 `scalim.spec.ir`）
- 需要在文档中明确推荐路径优先级，否则用户会困惑
- 维护成本: 每新增一个公开类型，需要在 `types.py` + 领域入口两处添加

---

## 方案 D：激进重构 — 拆分为 `scalim.types` + `scalim._internal.typedefs`

### 思路

把 `typedefs.py` 物理拆分：公开类型移入 `scalim/types.py`，内部类型移入 `scalim/_internal/typedefs.py`。原 `typedefs.py` 变为纯重导出的 shim（过渡期）或直接删除（breaking）。

### 改动清单

| 文件 | 操作 |
|------|------|
| `src/scalim/types.py` **(新建)** | Tier 1 + Tier 2 类型的**定义**（不是 re-export，是 SSOT 本体搬过来） |
| `src/scalim/_internal/typedefs.py` **(新建)** | Tier 3 内部类型定义 |
| `src/scalim/typedefs.py` | **删除**或改为 shim（纯 re-export，标注 deprecated） |
| 52 个内部文件 | `from ..typedefs import X` 改为 `from ..types import X` 或 `from .._internal.typedefs import X` |
| 16 个外部文件 | `from scalim.typedefs import X` 改为 `from scalim.types import X` |
| `src/scalim/spec/ir/aliases/__init__.py` | import 路径更新 |
| `src/scalim/dsl/by_yaml/__init__.py` | 可选重导出 |
| `src/scalim/spec/ir/__init__.py` | 可选重导出 |
| 所有其他入口 | 可选重导出 |
| 常量搬移 + 测试更新 | 同上 |

### `types.py` 成为 SSOT

```python
"""scalim 公开类型 — 这里是定义本体,不是 re-export."""

from decimal import Decimal
from typing import Dict, Hashable, List, Mapping, Sequence, Set, Tuple, Union
from .vendor.compact import StrEnum
from .vendor.compact.typing_extensionsx import Literal

FieldValue = Union[int, float, Decimal, str, bool, None]
RowData = Mapping[str, FieldValue]
# ... 所有 Tier 1 + Tier 2 类型定义

__all__ = [...]
```

### `_internal/typedefs.py` 仅含内部类型

```python
"""框架内部类型别名 — 不属于公开 API."""

from ..types import RuntimeValue
from typing import Dict, Tuple

LoaderCallArgs = Tuple[RuntimeValue, ...]
LoaderCallKwargs = Dict[str, RuntimeValue]
LoaderCallParams = Tuple[LoaderCallArgs, LoaderCallKwargs]
```

### 优劣分析

**优势**:
- **架构最清晰**: 公开/内部边界物理隔离，不是靠 `__all__` 软约定
- SSOT 只有一份（`types.py`），不存在"typedefs 定义，types re-export"的双层间接
- `scalim._internal.typedefs` 信号明确：下划线前缀 = 不要碰
- 未来维护最轻松：新增公开类型加 `types.py`，内部类型加 `_internal/typedefs.py`

**劣势**:
- **改动量巨大**: 52 个内部文件 + 16 个外部文件 = 68 个文件需要更新 import 路径
- **Breaking change**: `from scalim.typedefs import ...` 失效（除非保留 shim）
- 如果保留 `typedefs.py` 作为 shim，则 shim 本身成为维护负担
- `from ..types import X` 在内部使用时与 stdlib `types` 的 shadow 风险更高
- `spec.ir.aliases` 中 `from ....typedefs import` 的四层相对导入需要改为 `from ....types import`

### 风险缓解: 过渡 shim

如果希望保留向后兼容一段时间：

```python
# src/scalim/typedefs.py (过渡 shim)
"""[Deprecated] 请改用 scalim.types. 此模块将在 v2.0 移除."""
import warnings as _w
_w.warn("scalim.typedefs is deprecated, use scalim.types", DeprecationWarning, stacklevel=2)

from .types import *  # noqa: F401,F403
from ._internal.typedefs import *  # noqa: F401,F403
```

注意：此 shim 会在 **import 时** 触发 DeprecationWarning（模块级代码），这是可行的。但 `import *` 在 Python 3.6 下结合 `__all__` 行为需要测试验证。

---

## 方案对比总表

```
                      方案 A        方案 B        方案 C        方案 D
                      (最小侵入)   (新 types)   (A+B 组合)   (激进重构)
  ─────────────────────────────────────────────────────────────────────
  改动文件数           ~8           ~4+          ~12+          ~70+
  Breaking changes     0            0            0             是(可缓解)
  用户可发现性         中           高           最高          高
  概念清晰度           中           高           中(多路径)   最高
  维护成本             低           中           高            低(长期)
  "去哪找类型"的答案   散落各入口   scalim.types  都行         scalim.types
  内部/公开边界         软(__all__)  软(__all__)   软(__all__)   硬(物理隔离)
  导入路径数量         2            2            3             1(+shim=2)
  运行时开销           0            0            0             0
  Python 3.6 兼容     是            是            是            是
```

---

## 我的推荐

**短期（当前版本）**: 方案 B — 新建 `scalim.types`，typedefs 保留但不推荐。改动量可控，用户体验大幅提升，且为将来的方案 D 铺路。

**长期（major version bump 时）**: 方案 D — 在 major version 中完成物理拆分，删除 typedefs shim。此时 68 个文件的 import 迁移可以用自动化工具完成。

**不推荐方案 C**: 三条导入路径的灵活性看似好，但带来的文档负担和风格一致性问题不值得。

---

## 实施顺序（以方案 B 为例）

1. `typedefs.py` 添加 `__all__`
2. 新建 `types.py`，从 typedefs + warningsx + aliases 聚合
3. 搬移 `DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY` 到 load_ref 内部
4. `__init__.py` 导出 `ScalimExperimentalWarning` + docstring 更新
5. 更新 16 个外部文件的 import 路径（可选，建议做）
6. 更新文档/示例使用新路径
7. `just qa` 验证全部通过
