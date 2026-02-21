# `scalim/vendor/` provenance & update policy

本目录用于存放 **内嵌(vendored)** 的第三方代码片段与 **本地实现(local re-implementation)**,其目标通常是:
- 平滑跨 Python 3.10+ 的标准库差异(例如 `enum.StrEnum`, `typing.Self`/`override`)
- 避免将体积较大/非必需的库变成硬依赖(例如 `rich`、`jinja2` 等)

## Governance rules

- `scalim/vendor/*` 下每个子模块 MUST 在本文档中登记 provenance(来源、版本/commit pin、许可证、局部修改点与更新策略).
- 若存在从上游复制的代码片段,必须给出明确的上游链接与 commit pin,并注明许可证类型.
- 只做“最小必要”内嵌与修改,避免把 vendor 目录变成杂物箱.

---

## `compact/`

**Purpose:** 兼容性小组件(typing/enum/import).

### `compact.__init__.py` / `StrEnum` fallback

- **Source (upstream):** CPython `Lib/enum.py` 的 `StrEnum` 实现片段
  - URL: https://github.com/python/cpython/blob/1ae900424b3c888d2b2cc97e6ef780717813d658/Lib/enum.py#L1365
  - **Pin:** `1ae900424b3c888d2b2cc97e6ef780717813d658`
- **License:** PSF License(Python Software Foundation License, CPython)
- **Local modifications:** 以“最小必要”为原则做包装与适配(例如导入、类型注解与兼容 `Self`).
- **Usage:** 通过 `from scalim.vendor.compact import StrEnum` 被使用(例如 `scalim/typedefs.py`, `scalim/planning/operators.py`).
- **Update strategy:**
  1) 当升级 Python 基线或发现 enum 相关 bug/安全问题时,到上游定位最新 `StrEnum` 实现.
  2) 对比差异并仅同步该片段所需的最小变更(避免引入不必要逻辑).
  3) 运行 `uv run pytest` 验证兼容.

### `compact/typing_extensionsx.py`

- **Source:** 本仓库实现(compat shim),不是上游镜像.
- **Upstream dependency (runtime):** `typing_extensions`(生产环境可能较旧,例如 4.1.1)
- **License:** N/A(本地实现;依赖的 `typing_extensions` 许可遵循其自身分发方式)
- **Local modifications / policy:**
  - 提供 `override`/`Literal`/`Self`/`TypedDict` 的兼容导出,以覆盖 Python 3.10+ 的标准库 typing 演进差异与旧版 `typing_extensions`.
  - `scalim/` 内 **新增** typing_extensions 新特性时,必须先在 `typing_extensionsx.py` 增加 shim,再在各模块中引用.
- **Usage:** 被广泛用于类型与装饰器兼容(例如 hooks/ob/execution/sinks/dsl 等模块).
- **Update strategy:**
  1) 当需要引入新的 typing_extensions 能力时,先评估最老生产组合(例如 Py3.10 + typing_extensions 4.1.1)是否可用.
  2) 仅添加“向后兼容”的最小 shim(ImportError fallback),避免扩大运行时行为.
  3) 运行 `uv run pytest` 验证.

### `compact/importlibx.py`

- **Source:** 本仓库实现(统一 optional dependency import + 测试 seam).
- **License:** N/A(本地实现)
- **Usage:** 可选依赖导入点(例如 `scalim/sinks/sink_pandas.py`, `scalim/sinks/sink_excel.py`).
- **Update strategy:** 保持错误信息与 seam 稳定;如需新增 optional 依赖,优先复用 `require_optional_dependency`.

---

## `literich/`

**Purpose:** 轻量级终端美化输出(表格/面板),用于可观测性 presets 的文本渲染.

- **Source:** 本仓库实现(轻量实现,非上游镜像).
- **Related projects (conceptual alternatives):** `rich`(可选依赖)
- **License:** N/A(本地实现)
- **Local modifications / policy:** 以稳定输出与最小功能集为目标;避免扩展为完整 TUI 框架.
- **Usage:** 主要在 `scalim/ob/presets/*` 与 `scalim/ob/metrics.py` 中使用;回归测试见 `tests/test_literich.py`.
- **Update strategy:**
  1) 若渲染出现对齐/宽度问题,优先修复 `unicodedata.east_asian_width` 的显示宽度逻辑.
  2) 保持输出格式相对稳定(避免破坏日志对比/对拍).
  3) 运行 `uv run pytest` 验证.
