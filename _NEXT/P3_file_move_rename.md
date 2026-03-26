# P3: scalim 内部模块封装 — 文件移动/重命名（单包单批，前后快照对比）

> **来源方案**：
> - `source_plans/4_package-encapsulation-refactor.plan.md` — **方案 C（混合策略，推荐）**：sinks→`_internal/`（文件多+需重命名）、events→`_`前缀（仅 4 文件）、hooks→`_`前缀+barrel、utils→移入 `_internal/`
> - `source_plans/1_api_surface_governance.plan.md` — 决策点 3-B2：spec/ir 叶子模块重命名为 `_` 前缀
> - `source_plans/3_re-export_chain_audit.plan.md` — 决策 3（relation_signature shim 清理，采纳方案 A：删除 shim）
> - `source_plans/2_typedefs_audit_plans.plan.md` — 共同前提 P2：`DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY` 搬离 typedefs

## 项目约束

- Python 3.6 兼容；`src/scalim/` 内使用相对导入
- 格式化：ruff（4-space indent, line length 140, double quotes）
- `if TYPE_CHECKING:` 仅用于 type-only imports/aliases
- 质量门禁：`just qa` 必须在每包改动后通过
- 测试覆盖率目标 100%，不得降低现有覆盖率

## 核心原则

1. **MUST: barrel 已在 P2 中填充完毕** — 本步骤的前提
2. **每次只处理一个包** — 完成后立即 `just qa`
3. **使用 `git mv`** — 保留文件历史
4. **类型检查不可中断** — 移动文件后所有 `TYPE_CHECKING` 块中的导入路径也要更新

## 前置快照

```bash
# 保存当前 API 表面快照
python -c "
import ast, json, pathlib
result = {}
for p in pathlib.Path('src/scalim').rglob('*.py'):
    try:
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == '__all__':
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            result[str(p)] = [
                                elt.s for elt in node.value.elts
                                if isinstance(elt, ast.Str)
                            ]
    except: pass
with open('.tmp/api-snapshot-before.json', 'w') as f:
    json.dump(result, f, indent=2)
"
just qa  # 确认基线通过
```

---

## 包 A: `sinks/` → `_internal/` 子目录

### Step 1: 创建目录 + 移动文件

```bash
mkdir -p src/scalim/sinks/_internal
touch src/scalim/sinks/_internal/__init__.py

cd src/scalim/sinks
git mv sink_base.py _internal/base.py
git mv sink_csv.py _internal/csv.py
git mv sink_excel.py _internal/excel.py
git mv sink_memory.py _internal/memory.py
git mv sink_pandas.py _internal/pandas.py
git mv sink_rows.py _internal/rows.py
```

### Step 2: 更新 barrel `__init__.py` 的 import 路径

```python
# BEFORE (P2 已填充)
from .sink_base import BaseSink, BaseRowSink, ...
from .sink_csv import CSVSink, ...
# AFTER
from ._internal.base import BaseSink, BaseRowSink, ...
from ._internal.csv import CSVSink, ...
```

### Step 3: 更新 `_internal/` 内文件的相对导入

在 `_internal/csv.py`, `_internal/excel.py` 等中：

```python
# BEFORE
from .sink_base import BaseSink
# AFTER
from .base import BaseSink
```

### Step 4: 更新 `src/scalim/` 内其他包的引用

搜索所有 `from ..sinks.sink_` 导入，改为走 barrel：

```python
# BEFORE
from ..sinks.sink_csv import CSVSink
# AFTER
from ..sinks import CSVSink
```

### Step 5: 更新 `TYPE_CHECKING` 块

同步更新所有 `if TYPE_CHECKING:` 块中引用 sinks 子模块的导入路径。

### Step 6: 更新外部引用

```bash
rg "from scalim\.sinks\.sink_" tests/ packages/ notebooks/ --files-with-matches
```

将每个匹配改为 barrel 路径：`from scalim.sinks import X`

### Step 7: 验证

```bash
just qa
# 对比 API 表面快照
```

---

## 包 B: `events/` → 加 `_` 前缀

### Step 1: 重命名

```bash
cd src/scalim/events
git mv event.py _event.py
git mv events.py _events.py
git mv catalog.py _catalog.py
git mv attribution.py _attribution.py
```

### Step 2: 更新 barrel `__init__.py`

```python
# BEFORE
from .event import Event, ...
# AFTER
from ._event import Event, ...
```

### Step 3: 更新包内相对导入

### Step 4: 更新 `src/scalim/` 内其他包的引用（改为走 barrel）

### Step 5: 更新 `TYPE_CHECKING` 块

### Step 6: 更新外部引用

### Step 7: 验证 — `just qa`

---

## 包 C: `hooks/` → 加 `_` 前缀

### Step 1: 重命名

```bash
cd src/scalim/hooks
git mv base.py _base.py
git mv dispatch.py _dispatch.py
```

### Step 2-7: 同包 B 模式

---

## 包 D: `utils/` → 移入 `_internal/utils/`

### Step 1: 移动

```bash
mkdir -p src/scalim/_internal/utils
touch src/scalim/_internal/utils/__init__.py

cd src/scalim
git mv utils/converters.py _internal/utils/converters.py
git mv utils/excel.py _internal/utils/excel.py
git mv utils/graph.py _internal/utils/graph.py
git mv utils/iterables.py _internal/utils/iterables.py
git mv utils/json_like.py _internal/utils/json_like.py
# relation_signature.py 和 relation_diagnostics.py 留到 Phase 3 处理
```

### Step 2: 保留 `utils/__init__.py` 为空壳（或仅转发极少量符号）

### Step 3-7: 更新引用 + 验证

---

## 包 E: `spec/ir/` 叶子模块 → 加 `_` 前缀

### Step 1: 重命名

```bash
cd src/scalim/spec/ir
git mv demand.py _demand.py
git mv fields.py _fields.py
git mv helpers.py _helpers.py
git mv relations.py _relations.py
git mv source_contracts.py _source_contracts.py
git mv sources.py _sources.py
git mv workflow.py _workflow.py
```

### Step 2: 更新 `spec/ir/__init__.py` 的 import 路径

### Step 3-7: 更新引用 + 验证

---

## 包 F: 顶层文件整理

### `warningsx.py` → `_internal/warningsx.py`

```bash
git mv src/scalim/warningsx.py src/scalim/_internal/warningsx.py
```

更新所有 `from ..warningsx import` / `from .warningsx import` 引用。确保 `scalim.__init__` 中的 `ScalimExperimentalWarning` re-export 路径正确。

### 删除 `execution/executor/helpers/relation_signature.py` shim

```bash
git rm src/scalim/execution/executor/helpers/relation_signature.py
```

修改 5 个消费文件改为从 `utils/relation_signature.py` 导入。

---

## 失败回退策略

如果 `just qa` 失败：

1. `git stash` 保存当前改动
2. 分析失败原因，区分：
   - a) 导入路径遗漏（补充遗漏的路径更新）
   - b) 测试中硬编码了旧路径（更新测试的 import，不改测试逻辑）
   - c) 类型检查失败（检查 `TYPE_CHECKING` 块）
3. `git stash pop` 恢复，修复后重新 `just qa`

## 完成标准（每包）

- `just qa` 通过
- `git diff --stat` 显示：仅目标包内文件重命名 + import 路径更新
- 无测试逻辑被修改（只改了 import 行）
- API 表面快照前后一致（barrel `__init__.py` 的 `__all__` 不变）
