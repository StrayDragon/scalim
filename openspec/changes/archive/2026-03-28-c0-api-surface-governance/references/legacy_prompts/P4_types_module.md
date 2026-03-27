# P4: 新建 `scalim/types.py` 公开类型聚合入口

> **来源方案**：
> - `source_plans/2_typedefs_audit_plans.plan.md` — **方案 B（新建 `scalim.types`，推荐短期方案）**：types.py 内容设计、用户导入体验、优劣分析
> - `source_plans/2_typedefs_audit_plans.plan.md` — 共同前提 P3（向后兼容别名 RowId/RowIdSeq/RowIdList 处理）、P4（ScalimExperimentalWarning 导出）
> - `source_plans/1_api_surface_governance.plan.md` — 决策点 5（events/hooks 标记为 Provisional，不建 facade）

## 项目约束

- Python 3.6 兼容；`src/scalim/` 内使用相对导入
- 格式化：ruff（4-space indent, line length 140, double quotes）
- `if TYPE_CHECKING:` 仅用于 type-only imports/aliases
- 质量门禁：`just qa`
- 测试覆盖率目标 100%

## 核心原则

1. **`types.py` 是纯 re-export 模块** — 不定义任何新类型
2. **`typedefs.py` 保留不动** — 52 个内部文件的相对导入不受影响
3. **类型检查器必须能通过 `types.py` 解析所有导出类型**
4. **逐步验证**：先创建 → 验证 runtime import → 验证 `just qa`

## 前置条件

- P1 已完成：`typedefs.py` 已有 `__all__`
- P3 已完成（如果 `warningsx.py` 已移动到 `_internal/`，需调整导入路径）

## Step 1: 分析 `typedefs.py` 当前 `__all__`

```bash
python -c "
from scalim.typedefs import __all__ as ta
print('typedefs exports:', len(ta), ta)
"
```

## Step 2: 创建 `src/scalim/types.py`

```python
"""scalim 公开类型入口.

所有用户可见的类型别名、Literal 类型、枚举均从此处导出.
内部 SSOT 为 typedefs.py，本模块仅做聚合 re-export.

Usage::

    from scalim.types import RowData, FieldValue, ParallelMode
"""
# 数据类型
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

# Literal 类型
from .typedefs import (
    FieldPresentationKind,
    KeyNormalizationMode,
    ParallelMode,
    PerformanceReportFormat,
    RelationLookupResult,
    RelationReportFormat,
)

# Callable 类型 (来自 spec.ir.aliases)
from .spec.ir.aliases import (
    LoaderExtractor,
    LoaderParamsBuilder,
    LoaderResultMapCallable,
    LookupKeyCast,
    LookupKeySpec,
    MainSourceRowIterableCallable,
    NormalizedLookupKeySpec,
)

# Warning
from .warningsx import ScalimExperimentalWarning  # 如果已移到 _internal，调整路径

__all__ = [
    # 数据类型
    "BusinessKey",
    "FieldValue",
    "LoaderResult",
    "LookupKey",
    "RecordKey",
    "RecordKeySeq",
    "RowData",
    "RuntimeValue",
    "SinkRowKey",
    "SinkRowKeySeq",
    "SourceSpecIrCacheMode",
    "StaticParams",
    # Literal 类型
    "FieldPresentationKind",
    "KeyNormalizationMode",
    "ParallelMode",
    "PerformanceReportFormat",
    "RelationLookupResult",
    "RelationReportFormat",
    # Callable 类型
    "LoaderExtractor",
    "LoaderParamsBuilder",
    "LoaderResultMapCallable",
    "LookupKeyCast",
    "LookupKeySpec",
    "MainSourceRowIterableCallable",
    "NormalizedLookupKeySpec",
    # Warning
    "ScalimExperimentalWarning",
]
```

> **注意**：以上符号列表需根据 `typedefs.py` 实际 `__all__` 和 `spec.ir.aliases.__all__` 校对。`from .warningsx import` 路径需根据 P3 是否已移动来调整（可能是 `from ._internal.warningsx import`）。

## Step 3: 验证 — 运行时导入

```bash
python -c "
from scalim.types import __all__ as ta
for name in ta:
    obj = getattr(__import__('scalim.types', fromlist=[name]), name)
    print(f'  {name}: {type(obj).__name__}')
print(f'Total: {len(ta)} symbols, all importable')
"
```

## Step 4: 验证 — 类型检查器兼容性

```bash
cat > .tmp/type_check_types.py << 'EOF'
from scalim.types import (
    RowData, FieldValue, LoaderResult, ParallelMode,
    LoaderResultMapCallable, ScalimExperimentalWarning,
)

def example(data: RowData, mode: ParallelMode) -> LoaderResult:
    ...

reveal_type(example)
EOF

# 如果有 mypy
mypy .tmp/type_check_types.py --ignore-missing-imports 2>/dev/null && echo "mypy OK" || echo "mypy issues"
rm -f .tmp/type_check_types.py
```

## Step 5: 验证 — 门禁

```bash
just qa
```

## Step 6: 更新 `scalim/__init__.py` docstring

在 `__init__.py` 的模块 docstring 中添加 `scalim.types` 作为推荐类型入口。

## 完成标准

- `just qa` 通过
- `from scalim.types import X` 对所有 `__all__` 符号可用
- `from scalim.typedefs import X` 旧路径仍可用（零破坏）
- 新建文件仅 1 个：`src/scalim/types.py`
- 无测试文件被修改
