## Context

YAML DSL 在 parse 前支持 LiteJinja2 预编译：当调用方显式提供 `template_vars` 时，会对 YAML 文本执行模板渲染（`maybe_precompile_yaml_text`）。

As-Is 行为（高危脚枪）：

- LiteJinja2 变量解析支持：
  - 任意属性访问（含 `__dunder__`）
  - 无参方法调用（以 `()` 结尾的属性会被执行）
- 因此只要调用方在 `template_vars` 中注入“带能力/副作用”的对象（例如 `pathlib.Path`、文件对象、客户端实例），YAML 模板就能在渲染阶段触发副作用（读文件、删文件等）。

关键代码路径：

- 入口：`src/scalim/dsl/by_yaml/config_parsing/template_precompile.py::maybe_precompile_yaml_text`
- LiteJinja2 变量解析：`src/scalim/vendor/litejinja2/__init__.py::Template._get_variable`（属性访问 + `()` 调用）

约束：

- `src/scalim/` 运行时需兼容 Python 3.6。
- 本变更属于安全语义收敛：默认必须 sandbox；可信场景允许显式 opt-in 恢复 legacy 行为，但必须强告警。

## Goals / Non-Goals

**Goals:**

- 当且仅当 `template_vars is not None` 时启用预编译（保持现有“显式启用”语义）。
- 默认 sandbox（安全默认值）必须满足：
  - 禁止无参方法调用（`x.y()`）在渲染阶段执行
  - 禁止访问以下划线开头属性（含 `__dunder__`）
  - 允许 dict/list/tuple 的 key/index 访问（满足常见替换需求）
- 提供显式 legacy/trusted 模式：
  - 仅当调用方显式 opt-in 才允许属性访问与方法调用
  - 启用时必须发出强 warning（避免生产误用）
- 增加 `template_vars` 输入护栏（降低误注入风险）：
  - 默认仅允许 JSON/YAML-like 类型（`None/bool/int/float/str/list/tuple/dict`），遇到其它类型 fail-fast（错误信息不包含值明细）

**Non-Goals:**

- 不在本变更中实现“安全过滤器集合”（`tojson`/`toyaml` 等），也不提供“安全函数白名单”。
- 不试图让 sandbox 支持复杂表达式（例如字符串方法链、对象方法调用）；sandbox 目标是“受控替换”而非“脚本执行”。
- 不改变 YAML 解析/校验语义；仅改变“预编译阶段的可表达能力边界”。

## Decisions

### 1) sandbox 的实现位置：在 LiteJinja2 变量解析处做硬约束

**决策：**

- 在 `Template._get_variable` 的属性访问/方法调用逻辑处引入 sandbox gate：
  - 当 sandbox 模式启用时：
    - 任意 `part.endswith("()")` → 直接 fail-fast（抛 `TemplateError`，错误信息指向“method call 被禁止”）
    - 任意 `part.startswith("_")` 或 `method_name.startswith("_")` → fail-fast（抛 `TemplateError`，指向“underscore attributes 被禁止”）
- 该 gate 必须覆盖：
  - dict 路径（当前实现允许 `hasattr(dict, ...)` 并调用）
  - 非 dict 路径（普通 getattr + callable 调用）

**备选：**

- 仅通过“净化 template_vars 为纯 JSON-like”来间接 sandbox：不足以阻止对 `str/int/...` 的 `__class__` 自省链与 `__subclasses__()` 等经典逃逸路径（仍需要禁用 `_` 属性与方法调用）。
- 通过正则扫描模板文本禁止 `()`/`__`：不可靠且容易漏边界（例如多段属性链、空白、过滤器参数等）。

### 2) legacy/trusted 模式：显式 opt-in 且强告警

**决策：**

- 在 `maybe_precompile_yaml_text` 与高层入口（建议：`RunOptions`）增加显式开关：
  - 默认 `sandbox`（安全）
  - 显式 `legacy`（不安全；允许属性访问与无参方法调用）
- legacy 模式必须发出 warning：
  - 至少日志 warning（带稳定前缀，便于 grep/过滤）
  - 可选：诊断事件（但不得依赖其可见性作为唯一提示通道）

**理由：**

模板预编译的常见用法是“字符串替换”，sandbox 足够；少数确实需要调用方法/访问对象属性的场景应显式声明为可信并承担风险。

### 3) `template_vars` 输入护栏：默认只允许 JSON/YAML-like

**决策：**

- 在进入渲染前递归校验 `template_vars`：
  - 仅允许：`None/bool/int/float/str/list/tuple/dict`（dict key 必须可转为 str）
  - 发现其它类型 → fail-fast（错误信息包含类型名与“路径”，不包含值明细）
- 该护栏作为 defense-in-depth：即使 legacy 模式存在，也能减少误把“带能力对象”直接注入的概率。

**备选：**

- 非安全类型自动 `str()` 降级：虽然更宽松，但会把“误注入能力对象”静默转为字符串，可能掩盖真实配置错误；默认不采用。

## Risks / Trade-offs

- [BREAKING] 既有依赖 `{{ x.y() }}` 或访问对象属性的模板在默认 sandbox 下会失败 → 缓解：提供 legacy 显式开关，并在错误中提示如何启用（含风险说明）。
- [兼容性] 修改 vendor LiteJinja2 可能影响其它使用点 → 缓解：将 sandbox/legacy 控制做成“可选参数”，并且仅由 YAML DSL 预编译入口默认启用；为 vendor 行为补齐单测。
- [误解] 用户可能认为 “template_vars 只是字符串替换” 而忽略风险 → 缓解：文档与 warning 明确强调 legacy 模式不安全；sandbox 为默认。

## Migration Plan

1. 为 LiteJinja2 增加 sandbox/legacy 控制参数，并在 YAML 预编译入口默认启用 sandbox。
2. 在 `RunOptions`（或等价配置）暴露 legacy 显式 opt-in，并在启用时强告警。
3. 增加回归测试：
   - sandbox 默认拒绝 `x.y()` 与 `_` 属性
   - legacy 模式允许上述语法且 warning 可观测
   - 常见替换（变量、dict key、list index）保持可用
4. 运行 `just openspec-check` 与 `just qa` 作为最终门禁。

## Open Questions

- legacy 模式开关命名：`template_vars_legacy_mode` vs `template_sandbox="legacy"`（倾向后者：语义更明确、易扩展）。
- `template_vars` 护栏的 “dict key 归一化” 策略：强制 `str(key)` 还是仅允许 `str`？（倾向 `str(key)`，但错误信息需指向原始类型。）
