---
name: API Compatibility Strategy
overview: 为 scalim 建立完整的 API 兼容性策略，涵盖稳定性标记体系、deprecation 流程、SemVer 策略、导入重定向兼容层、CI API 变更检测五大领域，每个领域给出多种方案及优劣对比。
todos:
  - id: api-status-markers
    content: 实现 API 稳定性标记体系 (docstring 约定 + _api_status.py 装饰器 + CI 扫描脚本)
    status: pending
  - id: deprecation-framework
    content: 实现 deprecation 框架 (ScalimDeprecationWarning + @deprecated 装饰器 + registry + CI 检查)
    status: pending
  - id: semver-changelog
    content: 建立 SemVer 策略文档 + CHANGELOG.md + 模块级稳定性标注
    status: pending
  - id: import-shim
    content: "实现导入重定向兼容层 (codegen shim 方案: 注册表 + 生成脚本 + drift-check)"
    status: pending
  - id: ci-api-diff
    content: 实现 CI API 变更检测 (api-surface snapshot + diff + justfile 集成 + PR 模板)
    status: pending
isProject: false
---

# scalim API 兼容性策略与版本演进规划

## 现状基线

- 版本 `0.4.1`（pre-1.0），单源头 `pyproject.toml` -> `_project_constants.py` -> `scalim.__version__`
- 已有 [public-api-surface-governance spec](openspec/specs/public-api-surface-governance/spec.md)，编目了公共入口
- 已有 `ScalimExperimentalWarning`（[warningsx.py](src/scalim/warningsx.py)），仅 `run_ir.py` 1 处使用
- 已有兼容别名 `RowId -> BusinessKey`（[typedefs.py](src/scalim/typedefs.py)），无 warning
- 零 `DeprecationWarning` 使用，无 CHANGELOG
- Python 3.6 运行时约束；`typing-extensions < 4.2` on py<3.7（排除 PEP 702 `@deprecated`）
- `sinks/` 无 `__init__.py`，用户直接 `from scalim.sinks.sink_csv import CsvSink`
- 已有 `just qa` 集成 drift-check、openspec-check、lint、test 等门禁

---

## 领域一：API 稳定性标记体系

### 方案 A：纯文档标记（docstring 约定 + `__all__`）

在 docstring 首行加结构化标签 `[public]` / `[experimental]` / `[internal]`，配合 `__all__` 白名单界定公共面。CI 用 AST 扫描验证覆盖率。

**实现要点**：

- 约定 docstring 格式：`"""[public] 执行层入口."""`
- 新增 `scripts/check-api-stability-tags.py`，AST 扫描所有已编目模块的 `__all__` 符号，断言每个都有标签
- 集成到 `just qa` 的 `quick-check-only-py` 链

**优势**：

- 零运行时开销
- Python 3.6 完全兼容
- 可由 CI 强制执行
- 自然延伸已有 docstring 约定（如 `[兼容别名]` 已在 typedefs 使用）

**劣势**：

- 无运行时强制力，用户 import internal 不会收到任何信号
- docstring 标签易被忽略/遗忘
- IDE 集成弱（不像装饰器能被 type checker 识别）

### 方案 B：轻量运行时装饰器

新增 `src/scalim/_api_status.py`，提供 `@public` / `@experimental` / `@internal` 装饰器，在函数/类上打 `_scalim_api_status` 属性。`@experimental` 在首次调用时发出 `ScalimExperimentalWarning`。

**实现要点**：

```python
# src/scalim/_api_status.py
import functools
import warnings
from .warningsx import ScalimExperimentalWarning

def public(obj):
    obj._scalim_api_status = "public"
    return obj

def experimental(obj):
    obj._scalim_api_status = "experimental"
    if callable(obj) and not isinstance(obj, type):
        _warned = set()
        @functools.wraps(obj)
        def wrapper(*args, **kwargs):
            if obj not in _warned:
                _warned.add(obj)
                warnings.warn(
                    "{!r} is experimental and may change".format(obj.__qualname__),
                    category=ScalimExperimentalWarning,
                    stacklevel=2,
                )
            return obj(*args, **kwargs)
        wrapper._scalim_api_status = "experimental"
        return wrapper
    return obj

def internal(obj):
    obj._scalim_api_status = "internal"
    return obj
```

**优势**：

- 运行时可查询（`getattr(fn, '_scalim_api_status', None)`）
- `@experimental` 主动提醒用户
- CI 可扫描确认所有公共符号都有标记
- Python 3.6 兼容

**劣势**：

- 对类的装饰无法拦截实例化（`__init_subclass__` 需 3.6+ 但不可靠；`__call__` 需 metaclass）
- 微量运行时开销（`@experimental` 的 wrapper）
- 需要逐步给所有公共符号加装饰器

### 方案 C：方案 A+B 分层组合（推荐）

- Layer 1：所有符号用 docstring 标签（低成本全覆盖）
- Layer 2：关键公共 API 入口加 `@public` / `@experimental` 装饰器（运行时信号）
- Layer 3：CI 扫描验证一致性（docstring 标签 <-> 装饰器 <-> `__all__`）

**优势**：兼得两者好处，渐进式推进
**劣势**：两套机制需保持同步，CI 复杂度稍高

---

## 领域二：Deprecation 流程

### 方案 A：`ScalimDeprecationWarning(DeprecationWarning)`

新建 warning 类继承 `DeprecationWarning`。

**实现要点**：

- 扩展 [warningsx.py](src/scalim/warningsx.py) 新增 `ScalimDeprecationWarning`
- 新增 `src/scalim/_deprecation.py` 提供 `@deprecated(since, removal, replacement)` 装饰器
- 新增 `src/scalim/_deprecation_registry.py` 集中追踪所有 deprecated 符号

```python
# warningsx.py 新增
class ScalimDeprecationWarning(DeprecationWarning):
    """scalim API 已弃用告警。继承 DeprecationWarning 以符合 Python 生态惯例。"""
```

```python
# _deprecation.py
def deprecated(since, removal, replacement=None):
    def decorator(obj):
        msg = "{!r} is deprecated since {} and will be removed in {}".format(
            obj.__qualname__, since, removal
        )
        if replacement:
            msg += "; use {!r} instead".format(replacement)
        # ... wrapper with warnings.warn(msg, ScalimDeprecationWarning, stacklevel=2)
        return wrapper
    return decorator
```

**优势**：

- 符合 Python 生态惯例（pytest 默认显示 `DeprecationWarning`）
- 开发者在测试中自动看到
- type checker 友好

**劣势**：

- 终端用户默认看不到（`DeprecationWarning` 在非 `__main__` 模块中被过滤）
- 需要在 CLI 入口手动 `warnings.filterwarnings("default", category=ScalimDeprecationWarning)` 才能让 CLI 用户看到

### 方案 B：`ScalimDeprecationWarning(FutureWarning)`

继承 `FutureWarning` 而非 `DeprecationWarning`。

**优势**：

- 终端用户和开发者**都**默认可见
- Python 官方推荐用于"面向终端用户的 deprecation"（[PEP 565](https://peps.python.org/pep-0565/)）

**劣势**：

- 不符合大多数库的惯例（大部分用 `DeprecationWarning`）
- pytest 的 `@pytest.deprecated_call()` 不会捕获 `FutureWarning`

### 方案 C：双 Warning 类

同时提供 `ScalimDeprecationWarning(DeprecationWarning)` 和 `ScalimFutureWarning(FutureWarning)`。前者用于"开发者 API 弃用"，后者用于"行为变更预告"。

**优势**：语义更精确
**劣势**：增加认知负担，两个类需要区分使用场景

### 版本窗口策略（三种方案）

- **方案 W1：N+2 移除**：v0.N 引入 warning -> v0.N+2 移除。窗口明确但 pre-1.0 可能太慢。
- **方案 W2：N+1 移除（pre-1.0 快速迭代）**：pre-1.0 期间 N+1 即可移除；1.0 后切换为 N+2。适合当前阶段。
- **方案 W3：日历驱动**：deprecated 后至少保留 6 个月。与版本号解耦，但需要在 registry 中记录日期。

### Deprecation Registry

在 `src/scalim/_deprecation_registry.py` 维护结构化注册表：

```python
DEPRECATED = {
    "scalim.typedefs.RowId": {
        "since": "0.5.0",
        "removal": "0.7.0",
        "replacement": "scalim.typedefs.BusinessKey",
    },
}
```

CI 脚本检查：

- 当前版本 >= `removal` 的条目是否已真正移除
- 当前版本 < `since` 的条目是否还未添加 warning

---

## 领域三：SemVer 策略

### 方案 S1：快速到 1.0（3-4 个 minor 版本）

0.4 -> 0.5（加框架）-> 0.6（清理）-> 1.0（稳定承诺）

**优势**：

- 快速给用户信心
- 缩短 pre-1.0 的"不稳定期"

**劣势**：

- 如果 API 面还有大变动，被 SemVer 绑住手脚
- 需要在 0.5-0.6 集中完成所有 breaking change

### 方案 S2：自然演进到 1.0

0.4 -> 0.5 -> ... -> 0.9 -> 1.0，每个 minor 可带 breaking change + migration guide

**优势**：

- 充足空间迭代
- 每个 minor 独立可控

**劣势**：

- 用户长期在"不稳定"状态
- 无明确 1.0 时间线

### 方案 S3：模块级稳定性承诺（推荐与方案 C 配合）

整包版本号继续 SemVer，但每个公共模块独立标记稳定性：

- `scalim.spec.ir` — stable since 0.3
- `scalim.dsl.by_yaml` — stable since 0.4
- `scalim.execution.adaptive` — experimental

**优势**：

- 精细控制，不被整包版本号卡住
- 与已有 `public-api-surface-governance` spec 自然衔接
- 用户可选择只依赖 stable 模块

**劣势**：

- 文档和沟通成本高
- 需要维护模块级稳定性矩阵

### CHANGELOG

无论哪种方案，都需要 CHANGELOG。推荐 [Keep a Changelog](https://keepachangelog.com/) 格式，放在 `CHANGELOG.md`。每个 entry 标注 `[BREAKING]` / `[Deprecated]` / `[Added]` 等。

---

## 领域四：导入重定向兼容层

### 方案 R1：Shim 模块（stub 文件）

旧模块变成只做 re-export + warn 的 shim。

```python
# scalim/sinks/sink_csv.py (变成 shim)
import warnings
from scalim.warningsx import ScalimDeprecationWarning
warnings.warn(
    "scalim.sinks.sink_csv is deprecated, use scalim.sinks.csv",
    ScalimDeprecationWarning, stacklevel=2,
)
from scalim.sinks.csv import *  # noqa: F401,F403
from scalim.sinks.csv import __all__  # noqa: F401
```

**优势**：

- 简单直白，Python 3.6 完全兼容
- import 时即 warn
- 每个 shim 独立，不互相影响

**劣势**：

- 大规模重构时 shim 文件数量爆炸
- 每个 shim 是手写样板代码（可用 codegen 缓解）

### 方案 R2：`sys.modules` 注入

在包 `__init__.py` 中集中注入旧路径到新模块的映射。

```python
# scalim/_compat_redirects.py
import sys, types, warnings

REDIRECTS = {
    "scalim.sinks.sink_csv": "scalim.sinks.csv",
}

def install_redirects():
    for old, new in REDIRECTS.items():
        # lazy redirect module
        ...
        sys.modules[old] = redirect_module
```

**优势**：

- 集中管理，无需真实 shim 文件
- 新增 redirect 只需改一行配置

**劣势**：

- `sys.modules` hack 调试困难
- 需要确保在用户任何 import 之前执行 `install_redirects()`
- 与 `importlib` / IDE 自动补全 / type checker 交互可能有 edge case
- Python 3.6 下 `ModuleType` 构造有已知坑

### 方案 R3：`__init__.py` + `__getattr__`（PEP 562）

在包 `__init__.py` 中用模块级 `__getattr__` 拦截旧名称。

**优势**：

- 最优雅，Python 标准机制
- 按需触发，零无用开销

**劣势**：

- **需要 Python 3.7+**，Python 3.6 不支持 PEP 562
- 只能拦截 `from package import name`，不能拦截 `import package.submodule`

### 方案 R4：Codegen Shim（推荐，方案 R1 的自动化版本）

维护一个 `_compat_redirects.toml`（或 `.py` 注册表），用 `scripts/gen-compat-shims.py` 自动生成 shim 模块。配合 drift-check 确保生成物与注册表同步。

```toml
# _compat_redirects.toml
[redirects]
"scalim.sinks.sink_csv" = { target = "scalim.sinks.csv", since = "0.5.0", removal = "0.7.0" }
```

**优势**：

- 集中管理（单一 SSOT）
- 自动生成 shim 减少样板
- 与已有 `gen-`* + `drift-check` 工具链一致
- Python 3.6 兼容

**劣势**：

- 需要新增 codegen 脚本
- 生成的 shim 文件需 commit（增加 repo 体积）

---

## 领域五：CI API 变更检测

### 方案 CI1：`__all__` Snapshot Diff

新增 `scripts/snapshot-api-surface.py`，提取所有已编目模块的 `__all__` 生成 `api-surface.snapshot.json`。CI 对比 main 分支的 snapshot，生成 diff 报告。

**实现要点**：

- AST 扫描提取 `__all__`（不需要 import，避免副作用）
- 输出 JSON：`{ "scalim.dsl.by_yaml": ["compile", "run", ...], ... }`
- Diff 分三类：Added（pass）、Removed（block / require deprecation）、Changed（warn）
- 集成到 `just qa` 作为 `api-surface-drift-check`

**优势**：

- 简单高效，与已有 drift-check 模式一致
- 不需要安装包，纯 AST
- 可在 PR comment 中自动输出 diff

**劣势**：

- 只能检测 `__all__` 变化，检测不到签名变更
- 需要维护 snapshot 文件

### 方案 CI2：签名级 Diff（AST 深度扫描）

除了 `__all__`，还提取每个公共符号的函数签名（参数名、默认值、类型注解）。

**优势**：

- 检测到参数重命名、默认值变更等 breaking change
- 更精确的 API 契约守护

**劣势**：

- AST 签名提取复杂度高（需处理类方法、property、overload 等）
- 可能产生误报（内部重构不影响行为但改了签名）
- 维护成本高

### 方案 CI3：Import Smoke + Runtime Introspection

在 CI 中实际 import 所有公共模块，用 `inspect` 提取签名，与 baseline 对比。

**优势**：

- 最真实（实际运行时视角）
- 能检测到动态生成的 API（如 `dsl.by_yaml` 的 lazy import）

**劣势**：

- 需要安装所有可选依赖
- 运行时有副作用风险
- CI 环境需要完整 Python 3.6+ 矩阵

### 方案 CI4：方案 CI1 + PR 模板（推荐起步方案）

`__all__` snapshot diff 配合 PR 模板中的 "API Impact" 检查项。

PR 模板新增：

```markdown
## API Impact
- [ ] 本 PR 不涉及公共 API 变更
- [ ] 新增公共符号：___
- [ ] 修改公共符号签名：___
- [ ] 弃用公共符号：___ （已加 deprecation warning + registry 条目）
- [ ] 移除公共符号：___ （已在 N-2 版本 deprecated）
```

**优势**：

- 低投入高回报
- 人工审查 + 自动化互补
- 可渐进增强到 CI2

**劣势**：

- 人工检查项可能被忽略
- 不如纯自动化可靠

---

## 推荐组合方案

基于"不在乎破坏性变更"的前提，推荐组合：

- **标记体系**：方案 C（分层：docstring + 装饰器）
- **Deprecation**：方案 A（继承 DeprecationWarning）+ 版本窗口 W2（pre-1.0 用 N+1）
- **SemVer**：方案 S3（模块级稳定性承诺）
- **导入重定向**：方案 R4（codegen shim）
- **CI**：方案 CI4（`__all__` snapshot + PR 模板），后续增强到 CI2

涉及的新增/修改文件清单：

- 新增 `src/scalim/_api_status.py`（装饰器）
- 修改 `src/scalim/warningsx.py`（新增 `ScalimDeprecationWarning`）
- 新增 `src/scalim/_deprecation.py`（`@deprecated` 装饰器）
- 新增 `src/scalim/_deprecation_registry.py`（注册表）
- 新增 `scripts/check-api-stability-tags.py`（CI 扫描）
- 新增 `scripts/snapshot-api-surface.py`（API surface 快照）
- 新增 `CHANGELOG.md`
- 修改 `justfile`（新增 `api-surface-drift-check`、`api-stability-tags-check`）
- 可选：新增 `scripts/gen-compat-shims.py` + `_compat_redirects.toml`
- 可选：PR 模板 `.github/pull_request_template.md`

