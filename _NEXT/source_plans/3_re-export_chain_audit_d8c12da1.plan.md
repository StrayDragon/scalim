---
name: Re-export Chain Audit
overview: 对 scalim 重导出链路的 4 个核心决策点分别提出全量方案，含优劣分析和决策矩阵，不回避破坏性变更。
todos:
  - id: decision-barrel
    content: 确认 barrel 定位策略 (A/B/C) 后，编写 canonical import path 映射表
    status: pending
  - id: decision-lazy
    content: "确认 spec.ir lazy 化策略 (建议 A: 保持 eager)"
    status: pending
  - id: impl-shim-cleanup
    content: 删除 relation_signature shim，修改 5 个文件 import 路径
    status: pending
  - id: impl-events-barrel
    content: 为 events/hooks/workflow 设计并实现 barrel __init__.py
    status: pending
  - id: impl-dsl-cache
    content: 为 dsl.by_yaml lazy import 添加 module-level cache
    status: pending
  - id: doc-canonical-table
    content: 生成 canonical import path 完整映射表文档
    status: pending
  - id: doc-migration-guide
    content: 编写迁移指南（deprecation 警告或直接破坏性变更）
    status: pending
isProject: false
---

# Scalim 重导出链路审计：全方案分析与决策矩阵

## 数据基底

先固定关键事实数据，所有方案分析基于此：

- `from scalim.spec.ir import` (barrel): **6 处** (notebooks/少数 test)
- `from scalim.spec.ir.<submod> import` (子模块直接): **~160 处** (tests/packages)
- `from scalim.events.<submod>`: 内部 src/ **~32 处**, tests **~70 处**
- `from scalim.hooks.<submod>`: 内部 src/ **~6 处**, tests **~30 处**
- `spec.ir` barrel 当前 **32 符号 / 7 子模块** eager; 遗漏 `workflow`/`helpers`/`source_contracts` 3 个子模块
- Python 3.6 无 `__getattr__` (PEP 562 = 3.7+)

---

## 决策 1：Barrel 定位策略

### 方案 A：Barrel = Canonical Entry Point (强制 barrel)

所有外部 / 测试代码统一从 barrel 导入，子模块路径标记为 `_internal` 或文档标注 internal-only。

**变更范围**：

- 改写 ~160 处 test 中的 `from scalim.spec.ir.binding import ...` 为 `from scalim.spec.ir import ...`
- 同理 events/hooks ~100 处
- barrel `__init__.py` 需覆盖所有公开符号（含目前遗漏的 `workflow`/`helpers` 子模块的符号）
- `spec.ir` barrel 需补入 ~15 个 workflow IR 类型 + helpers 函数

**优势**：

- 单一真相源：公开 API 表面清晰，一个文件就是全量 API 索引
- 重构自由度最大：子模块可任意移动/合并/拆分，只改 barrel 转发
- 文档 / IDE 补全体验最优：一个 import path 就能发现所有类型

**劣势**：

- **大规模迁移成本**：~260 处 import 需重写
- **barrel 膨胀**：spec.ir barrel 将从 32 膨胀到 ~47 符号（加 workflow IR 15 个）
- **导入成本**：barrel 强制 eager 加载所有子模块，即使只用一个类型
- **namespace 冲突风险**：当 barrel 太大时，不同子模块的同名符号可能冲突

### 方案 B：Barrel = Convenience Alias (承认现实)

Barrel 仅作为"快捷别名"，canonical path = 定义模块路径。Barrel 继续存在但不扩展。

**变更范围**：

- 把现有 6 处 `from scalim.spec.ir import` 改回子模块路径（或保留、不强制）
- 文档更新：推荐导入路径改为子模块级
- 无需修改 barrel `__init__.py`

**优势**：

- **零迁移成本**：现状即是目标状态
- **导入精细控制**：用户只加载所需子模块
- **避免 barrel 膨胀问题**

**劣势**：

- 用户必须知道内部模块结构（`spec.ir.binding` vs `spec.ir.demand` vs `spec.ir.sources`）
- 子模块重构会破坏所有消费者
- 公开 API 表面分散在 7+ 个文件中

### 方案 C：分层 Barrel (推荐考虑)

引入两级入口：

```
scalim.spec.ir           → 核心高频类型 barrel (~15-20 个)
scalim.spec.ir.binding   → binding 子域全量类型
scalim.spec.ir.workflow  → workflow IR 全量类型
...
```

规则：

- **高频符号** (DemandIr, FieldIr, SourceIr, MainSourceIr 等) 提升到顶级 barrel
- **低频 / 领域特定符号** 保留在子模块 (workflow IR, source_contracts, helpers)
- Canonical path = barrel 中有的从 barrel 导入，没有的从子模块导入
- 文档中用 "tier-1 / tier-2" 区分

**变更范围**：

- 精简 spec.ir barrel 至 ~15 个核心符号（移除 presentation 系列等低频类型）
- 或扩展 barrel 但文档标注层级
- 少量测试调整

**优势**：

- 平衡可发现性和导入成本
- 不需要大规模迁移
- 子模块重命名时只影响 tier-2 用户

**劣势**：

- 需要维护"哪些是 tier-1"的决策
- 两套导入路径并存，文档需清晰

---

## 决策 2：spec.ir Lazy 化

### 方案 A：保持 Eager (推荐)

现状不变。32 个 dataclass/alias 全部在 `import scalim.spec.ir` 时加载。

**优势**：

- 零复杂度
- 类型检查器完美兼容
- dataclass 本身极轻量（无 I/O、无重依赖）

**劣势**：

- 随 IR 类型增长线性增加（但增长速度很慢）

**适用条件**：IR 子模块不引入重依赖（当前满足）

### 方案 B：全量 Lazy (import_module wrapper)

仿照 `dsl.by_yaml` 模式，每个符号用 `import_module` + wrapper 延迟加载。

**变更范围**：

- 重写 [src/scalim/spec/ir/**init**.py](src/scalim/spec/ir/__init__.py)，32 个符号全部用 lazy wrapper
- 需要 `TYPE_CHECKING` 分支保持类型检查器可用
- Python 3.6 下无法用 `__getattr_`_，只能用显式 wrapper 函数（但 IR 类型是类不是函数，wrapper 会破坏 `isinstance` 检查）

**优势**：

- `import scalim.spec.ir` 变为 O(1)

**劣势**：

- **Python 3.6 下 dataclass 类型无法 lazy wrap**：wrapper 函数不能替代类（`isinstance(obj, DemandIr)` 会失败）
- 极高复杂度
- 收益极小（IR 全是轻量 dataclass）

**结论**：**技术上不可行** —— Python 3.6 下对类类型做 lazy 化会破坏 isinstance/类型系统

### 方案 C：按子模块分组 Lazy

不 lazy 单个符号，而是 lazy 整个子模块（仅在首次访问子模块时加载）。

```python
# 概念：import scalim.spec.ir 不加载子模块
# 但 scalim.spec.ir.binding 首次访问时加载 binding 子模块
```

**变更范围**：

- 删除 barrel 的 `from .binding import ...` 等语句
- barrel 变为空或只含 `__all__` 声明

**优势**：

- `import scalim.spec.ir` 变为几乎免费
- `from scalim.spec.ir.binding import BindingIr` 仍正常工作
- isinstance 不受影响

**劣势**：

- **破坏 `from scalim.spec.ir import DemandIr`** 这 6 处用法
- 本质上等于放弃 barrel（回到决策 1 方案 B）

---

## 决策 3：relation_signature Shim 清理

### 方案 A：删除 Shim，全部直接导入 SSOT

删除 [src/scalim/execution/executor/helpers/relation_signature.py](src/scalim/execution/executor/helpers/relation_signature.py)，所有消费者改为从 [src/scalim/utils/relation_signature.py](src/scalim/utils/relation_signature.py) 导入。

**变更范围**：

- 删除 `execution/executor/helpers/relation_signature.py`
- 修改 5 个文件的 import 路径：
  - `execution/executor/operators/load_ref/executor.py`
  - `execution/executor/runtime/runtime.py`
  - `execution/adaptive/strategy_unit.py`
  - `execution/adaptive/loadref_scheduler.py`
  - `execution/pipeline/base/pipeline.py`
- `planning/viz_schedule.py` 已直接使用 utils 路径，无需改

**优势**：

- 消除 100% passthrough shim
- 单一导入路径
- 减少一个文件

**劣势**：

- `execution` 子树向上依赖 `utils/`（但这已经是现实）
- 破坏任何直接 import 该 shim 的外部代码（但 `execution/executor/helpers/` 不是公开 API）

### 方案 B：保留 Shim，标记为 Internal Re-export

在 shim 文件头部加 docstring 说明它是 passthrough，不做变更。

**优势**：

- 零变更
- execution 子树有"局部入口"可依赖

**劣势**：

- 维护两条路径的 **all** 同步
- 新开发者可能困惑"该从哪导入"

### 方案 C：反转 SSOT 方向

把实现从 `utils/relation_signature.py` 移到 `execution/executor/helpers/relation_signature.py`，`utils/` 变为 shim（或删除）。

**变更范围**：

- 移动实现到 `execution/executor/helpers/`
- `utils/relation_signature.py` 变为 deprecated shim 或直接删除
- 修改 `planning/viz_schedule.py` 从 execution 子树导入

**优势**：

- 实现与主要消费者同一子树
- `utils/` 更干净

**劣势**：

- `planning/` 必须依赖 `execution/` 子树（架构上是否合理？planning → execution 依赖方向需确认）
- 如果 planning 不应依赖 execution，则此方案不可行

---

## 决策 4：events / hooks / workflow Barrel 设计

### 方案 A：Full Barrel (全量重导出)

```python
# events/__init__.py: 重导出全部 ~60 个公开符号
# hooks/__init__.py: 重导出全部 ~5 个公开符号
# workflow/__init__.py: 重导出 report + errors 中的公开类型
```

**events barrel 内容** (~60 符号)：

- `event.py`: Event, now_ts, generate_run_id (3)
- `events.py`: 28 个 *Event dataclass
- `catalog.py`: ~27 个 EVENT_* 常量 + EventDescriptor + 2 函数
- `attribution.py`: 3 个常量

**hooks barrel 内容** (5 符号)：

- BaseHook, Hook, HookManager, IExecutionHook, HookDispatchStrategy

**workflow barrel 内容** (4 符号)：

- WorkflowResult, WorkflowRunError, WorkflowRunOutcome, WorkflowConfigError

**优势**：

- 用户只需 `from scalim.events import Event, EVENT_LOADER_CALL, LoaderCallEvent`
- 与 spec.ir barrel 风格一致

**劣势**：

- events barrel 会有 ~60 符号（比 spec.ir 还大）
- 全部 eager 导入（但都是轻量 dataclass）

### 方案 B：Selective Barrel (精选重导出)

只提升高频符号到 barrel，低频保留在子模块。

```python
# events/__init__.py
from .event import Event, generate_run_id, now_ts
from .catalog import EventDescriptor, get_event_catalog
# 不重导出具体 EVENT_* 常量和 *Event dataclass

# hooks/__init__.py
from .base import BaseHook, HookManager, IExecutionHook
# 不重导出 HookDispatchStrategy (只有 1 处外部使用)

# workflow/__init__.py
from .report import WorkflowResult, WorkflowRunError, WorkflowRunOutcome
from .errors import WorkflowConfigError
```

**优势**：

- Barrel 小巧，导入成本低
- 核心类型可发现性好
- 不需要改测试代码（测试继续从子模块导入具体事件类型）

**劣势**：

- "哪些进 barrel / 哪些不进" 需要决策和文档
- 用户可能困惑为什么 Event 在 barrel 里但 LoaderCallEvent 不在

### 方案 C：Facade Module (门面模块，不用 barrel)

不在 `__init__.py` 做重导出，而是创建独立的 facade 模块：

```
scalim/events/public.py    → 公开 API 汇总
scalim/hooks/public.py     → 公开 API 汇总
```

**优势**：

- `__init__.py` 保持干净
- 明确区分"包入口" vs "公开 API 汇总"
- 不会意外被 `import scalim.events` 触发全量加载

**劣势**：

- 非常规 Python 模式，违反用户预期
- 额外文件

### 方案 D：保持现状 + 文档引导

不修改任何 `__init__.py`，但在文档中明确每个符号的推荐导入路径。

**优势**：

- 零代码变更
- 零风险

**劣势**：

- 用户体验不变（仍需知道内部模块名）
- 缺乏 IDE 可发现性

---

## 决策 5：dsl.by_yaml Lazy Import 优化

### 方案 A：Module-level Cache (模块级缓存)

```python
_entrypoints = None

def compile(*args, **kwargs):
    global _entrypoints
    if _entrypoints is None:
        _entrypoints = import_module("scalim.dsl.by_yaml.runtime.entrypoints")
    return _entrypoints.compile(*args, **kwargs)
```

**优势**：

- 避免每次调用的 import_module 开销
- 最小改动

**劣势**：

- 仍用绝对路径字符串

### 方案 B：Relative import_module + Cache

```python
_entrypoints = None

def compile(*args, **kwargs):
    global _entrypoints
    if _entrypoints is None:
        _entrypoints = import_module(".runtime.entrypoints", package=__package__)
    return _entrypoints.compile(*args, **kwargs)
```

**优势**：

- 相对路径，重命名更安全
- 有缓存

**劣势**：

- `import_module` 的 `package` 参数在 Python 3.6 下可能有边缘问题（需验证）

### 方案 C：保持现状

Python `sys.modules` 已提供缓存，`import_module` 第二次调用只是 dict lookup，实际开销微乎其微。

**优势**：

- 零变更
- 已验证可工作

**劣势**：

- 绝对路径字符串脆弱性不变

---

## 推荐组合方案

基于以上分析，最具一致性的组合是：


| 决策                       | 推荐                        | 理由                       |
| ------------------------ | ------------------------- | ------------------------ |
| 1. Barrel 定位             | **C: 分层 barrel**          | 平衡可发现性与迁移成本              |
| 2. spec.ir lazy          | **A: 保持 eager**           | Python 3.6 下对类 lazy 化不可行 |
| 3. relation_signature    | **A: 删除 shim**            | 明确 SSOT，消除歧义             |
| 4. events/hooks/workflow | **B: Selective barrel**   | 核心类型可发现，不膨胀              |
| 5. dsl.by_yaml lazy      | **A: Module-level cache** | 最小改动，有实际收益               |


如果不在乎破坏性，最激进的组合是：


| 决策                       | 推荐                                     | 理由            |
| ------------------------ | -------------------------------------- | ------------- |
| 1. Barrel 定位             | **A: 强制 barrel**                       | 最干净的公开 API 表面 |
| 2. spec.ir lazy          | **C: 按子模块 lazy** (= 放弃 barrel) 或 **A** | 取决于决策 1       |
| 3. relation_signature    | **A: 删除 shim**                         | 唯一合理选择        |
| 4. events/hooks/workflow | **A: Full barrel**                     | 一致性最强         |
| 5. dsl.by_yaml lazy      | **B: Relative + cache**                | 最健壮           |


注意：决策 1A (强制 barrel) 与决策 2C (按子模块 lazy) 互相矛盾——如果强制从 barrel 导入，barrel 必须 eager。