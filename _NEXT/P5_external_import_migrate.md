# P5: 外部导入路径迁移（按目录分批）

> **来源方案**：
> - `source_plans/6_api_compatibility_strategy.plan.md` — 领域四（导入重定向兼容层，方案 R4 codegen shim 暂缓，先手动迁移）
> - `source_plans/3_re-export_chain_audit.plan.md` — 决策 1-C（分层 barrel：canonical path 映射表）
> - `source_plans/4_package-encapsulation-refactor.plan.md` — 迁移路径 Phase 2（全量修改 tests/notebooks/packages 的外部导入路径）

## 项目约束

- Python 3.6 兼容
- 格式化：ruff（4-space indent, line length 140, double quotes）
- `if TYPE_CHECKING:` 仅用于 type-only imports/aliases
- 质量门禁：`just qa`
- 测试覆盖率目标 100%，不得降低现有覆盖率

## 核心原则

1. **只改 import 行，不改测试逻辑/断言/fixture**
2. **每个目录一批**：`tests/` → `packages/` → `notebooks/`，每批后 `just qa`
3. **旧路径仍可用**（barrel 已填充），本步骤是"推荐路径对齐"非强制
4. **保持 `TYPE_CHECKING` 一致性**

## 导入路径映射表

```python
# ━━━ sinks ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BEFORE                                      AFTER
"from scalim.sinks.sink_csv import X"       → "from scalim.sinks import X"
"from scalim.sinks.sink_memory import X"    → "from scalim.sinks import X"
"from scalim.sinks.sink_excel import X"     → "from scalim.sinks import X"
"from scalim.sinks.sink_pandas import X"    → "from scalim.sinks import X"
"from scalim.sinks.sink_base import X"      → "from scalim.sinks import X"
"from scalim.sinks.sink_rows import X"      → "from scalim.sinks import X"

# ━━━ events ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"from scalim.events.events import X"        → "from scalim.events import X"
"from scalim.events.event import X"         → "from scalim.events import X"
"from scalim.events.catalog import X"       → "from scalim.events import X"
"from scalim.events.attribution import X"   → "from scalim.events import X"

# ━━━ hooks ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"from scalim.hooks.base import X"           → "from scalim.hooks import X"
"from scalim.hooks.dispatch import X"       → "from scalim.hooks import X"

# ━━━ types（可选迁移）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"from scalim.typedefs import X"             → "from scalim.types import X"
"from scalim.warningsx import X"            → "from scalim import ScalimExperimentalWarning"

# ━━━ spec/ir（旧叶子路径已被 _ 封死）━━━━━━━━━━━━━━━━━━━━━━
"from scalim.spec.ir.demand import X"       → "from scalim.spec.ir import X"
"from scalim.spec.ir.fields import X"       → "from scalim.spec.ir import X"
# ... 其余叶子模块同理
```

## 批次 1: `tests/`

### 操作

```bash
# 1. 记录基线
just qa

# 2. 搜索待替换的导入
rg "from scalim\.(sinks\.sink_|events\.(event|events|catalog|attribution)|hooks\.(base|dispatch))" tests/ --files-with-matches

# 3. 逐文件替换 import 行
# 注意：不用 sed，逐文件手动确认替换

# 4. 验证
just qa
```

### 不迁移的例外情况

- 测试明确在测试某个内部模块本身的行为（如 `test_sink_csv.py` 专门测试 csv sink 内部逻辑）→ 保留深路径，但更新为 `_internal` 路径
- import 的符号不在 barrel `__all__` 中 → 保留深路径
- `TYPE_CHECKING` 块中的导入 → 同步迁移到 barrel 路径

## 批次 2: `packages/`

同批次 1 模式。

特别注意 `packages/scalim-misc` 中对 `utils.converters` 的引用，需改为 `_internal.utils.converters` 路径。

## 批次 3: `notebooks/`

同批次 1 模式。

## 失败处理

如果 `just qa` 中某个测试失败：

1. 检查是否因为测试 `import` 了一个未在 barrel `__all__` 中的符号
2. 如果是：回退该文件的改动，保留旧路径
3. 如果不是 import 问题：回退全部，调查原因后报告

**绝对不要修改测试的逻辑/断言/fixture 来适应 import 变更。**

## 完成标准

- `just qa` 通过
- `git diff` 确认只修改了 import 行（行首 `from scalim.` 或 `import scalim.`）
- 无测试逻辑/断言/fixture 被修改
- 覆盖率不变
