## Context

YAML DSL 的 Python callable 引用语法支持 class-style `module.path:attr`，并允许写成 `module.path:obj.method`。
这是 runtime 的常见写法（例如通过模块级单例对象暴露方法），但当前 editor semantics core 的静态 go-to-definition 仅支持：

- 模块顶层符号：`module.path:func` / `module.path:ClassName`
- class 内部符号：`module.path:ClassName.method`（仅当链路节点是 `ClassDef` 才继续向下索引）

当引用为 `module.path:obj.method` 且 `obj` 在 AST 中是 `Assign/AnnAssign`（例如 `obj = Klass()`）时，解析会在 `obj` 处停止并直接返回该赋值语句作为定义位置，无法跳到 `Klass.method`。

这在“可跳转性”上与用户直觉不一致：用户触发 definition 的目标通常是“真正被调用的实现”，而不是对象初始化语句。

## Goals / Non-Goals

**Goals:**
- 扩展静态解析覆盖：当 `module:obj.method` 中的 `obj` 可通过 AST 进行高置信度推断时，definition 优先跳转到真实实现（例如 `class Klass: def method`）。
- 多 locations 输出：definition 返回多个 locations（有序），把“推断的真实实现”放在第一个，把“obj 的定义/赋值”作为后续备选。
- 可诊断降级：当推断失败或不确定时，返回空或仅返回备选 locations，并提供明确 warnings（供 code action/排障命令展示）。
- 覆盖面靠 fixtures 回归保证：用 pytest fixtures 覆盖常见模式（同模块/跨模块导入/别名/注解/不支持的动态写法），确保行为稳定、可预测。

**Non-Goals:**
- 不做完整 Python 类型系统/数据流分析（不引入 mypy/pyright 等依赖）。
- 不执行用户代码，不导入模块、不运行表达式（保持“只读文件 + AST”边界）。
- 不复刻全量 import 语义（`*` import、复杂的 `sys.path`、环境 site-packages 发现等）——仅在 `python_roots` 可定位到的模块文件内做有限跟随。

## Decisions

### 1) 解析边界：仍然是 filesystem + AST（无执行、无全局副作用）

保持现有 contract：
- 仅允许文件读取与 `ast.parse`
- 模块定位仅通过 `python_roots` + `PathFinder.find_spec`
- 不改写 `sys.path`/`sys.meta_path`

### 2) 引入“轻量静态推断”以打通 `obj.method` → `Class.method`

在解析 `module:obj.method` 时，若 `obj` 的定义是模块顶层 `Assign/AnnAssign`，则尝试推断 `obj` 的“候选类”：

优先级（从高到低）：
1. **显式注解（AnnAssign / Assign + type comment）**
   - `obj: Klass = ...`
   - `obj: pkg.mod.Klass = ...`（支持简单 `Attribute` 链）
2. **构造调用（Assign value 是 Call）**
   - `obj = Klass()`
   - `obj = pkg.mod.Klass()`
   - `obj = alias.Klass()`（alias 由 `import pkg.mod as alias` 引入）
3. **类/对象别名（Assign value 是 Name/Attribute）**
   - `obj = Klass`（将 `obj` 视作类对象，继续解析 `.method`）
   - `obj = pkg.mod.Klass`

得到候选类引用后，再定位其 `ClassDef`（同模块或跨模块）并索引 `.method`：
- 同模块：在当前模块 AST symbol index 中寻找 `ClassDef`
- 跨模块：仅对 “import 可静态确定” 的场景跟随：
  - `from pkg.mod import Klass as K`（`K()` / `K.method`）
  - `import pkg.mod as m`（`m.Klass()` / `m.Klass.method`）

不支持（保持降级）：
- `obj = make()`（返回类型未知）
- `obj = get().sub`（动态属性）
- `obj = KlassFactory()[0]`（非简单 AST 形态）
- `obj = some_ref` 且 `some_ref` 不是高置信度 class/instance 来源

### 3) 多 locations 的排序与内容

对 definition 的返回值约定：
- **Location[0]**：最可能的“真实实现”定义（例如 `Klass.method`）
- **Location[1..]**：备选定位（例如 `obj = Klass()` 的赋值位置；必要时也可包含 `class Klass:` 的定义位置）

排序必须 deterministic，且“真实实现优先”。

### 4) 覆盖面用 fixture 驱动，避免只验证单一示例

新增一个“静态解析 fixtures 集合”（Python 模块 + YAML 片段 + 期望 locations 顺序），并用 pytest 参数化回归：

覆盖矩阵（v1 至少包含）：
- **Baseline**
  - `pkg.mod:func`（模块函数）
  - `pkg.mod:Class.method`（class 内方法）
- **本变更核心：obj.method**
  - 同模块：`obj = Klass()` → `Klass.method`
  - 同模块：`obj: Klass = ...` → `Klass.method`
  - 跨模块 from-import：`from a import Klass; obj = Klass()` → `a.Klass.method`
  - 跨模块 import-alias：`import a as aa; obj = aa.Klass()` → `a.Klass.method`
  - 类别名：`obj = Klass` / `obj = aa.Klass` → `Klass.method`
- **降级/失败可诊断**
  - `obj = factory()`（无法推断）→ 仅返回 `obj` 定义位置（或空）+ warnings
  - `obj = unknown.Klass()`（模块不可定位）→ 仅返回 `obj` 定义位置（或空）+ warnings
  - `obj` 非顶层符号（例如在函数内部赋值）→ 降级

同时保留最小 LSP server 端到端用例，验证 JSON-RPC 返回多个 Location 且顺序稳定。

## Risks / Trade-offs

- [误推断/误跳转] 轻量推断可能把 `obj` 归因到错误的类。
  - 缓解：仅对高置信度 AST 模式生效；返回多 locations 并保留 `obj` 定义作为兜底；对不确定路径输出 warnings。
- [性能] 跟随 import 需要解析额外模块文件。
  - 缓解：限定深度（仅解析 1 跳 import）；对同一模块文件的 AST 解析可做进程内缓存（按路径 + mtime），但必须保持 deterministic 与无副作用。
- [覆盖与复杂度失衡] 想覆盖“所有 Python 写法”会迅速膨胀。
  - 缓解：以 fixtures 驱动“真实用户常见写法”，逐步扩展；对不支持写法明确降级与提示。

## Migration Plan

无数据迁移；仅行为增强。注意：definition 返回多 locations 可能改变部分编辑器客户端的表现（通常是正向增强）。

## Resolved Questions

### 1) `class Klass` 是否作为常规 fallback location

决策：**仅当 method 未命中或无法确定时**返回 `class Klass` 作为备选 location。

- 当成功定位到 `Klass.method` 时，locations 保持尽可能短：`[Klass.method, obj-definition]`
- 当 `Klass` 可定位但 `method` 不存在/不确定时，locations 变为：`[class Klass, obj-definition]`，并输出 warnings（提示可能为继承/动态注入等）

### 2) imported object 的单跳跟随

决策：对 `from x import obj [as alias]` 形态，允许 **单跳** 跟随到 `x.obj` 的定义并继续推断（保持 AST-only，不执行导入）。

- locations 的顺序约定：`[real-implementation, import-site, origin-obj-definition]`
- 仅允许 1 跳，避免 re-export 链导致的复杂度与性能不可控；更深层次保持降级 + warnings
