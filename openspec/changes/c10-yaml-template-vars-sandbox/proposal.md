## Why

Scalim 的 YAML DSL 支持在 YAML parse 前对文本执行 LiteJinja2 预编译（当且仅当调用方显式提供 `template_vars` 时启用）。当前实现未做 sandbox，且 LiteJinja2 的变量解析支持：

- 任意属性访问（包括 `__dunder__`）
- 无参方法调用（以 `()` 结尾的属性会被 `getattr(... )()` 执行）

这会把“模板渲染”从纯文本替换升级为“可触发副作用的能力执行”。一旦调用方把带能力/副作用的对象注入 `template_vars`（例如 `pathlib.Path`、文件对象、某些 client 实例），YAML 文件就可以在渲染阶段触发文件读写/删除等行为，形成高危脚枪（误配置即失效），并且在“YAML 只是配置”的心理模型下很容易被误用到半可信输入场景。

### 最小复现（文件读取/破坏性副作用）

以下复现仅依赖当前仓库代码（无需额外依赖）：

```py
from pathlib import Path

from scalim.dsl.by_yaml.config_parsing.template_precompile import maybe_precompile_yaml_text

yaml_text = "x: {{ p.open().read() }}\n"
print(
    maybe_precompile_yaml_text(
        yaml_text,
        template_vars={"p": Path("/etc/hosts")},
        context_label="repro",
    )
)
```

在当前实现下，上述模板会把 `/etc/hosts` 内容注入到 YAML 文本中（信息泄露）。同理，若 `template_vars` 注入了指向某临时文件的 `Path`，则 `{{ p.unlink() }}` 可在渲染阶段直接删除文件（破坏性副作用）。

> 关键点：攻击/误用不需要在模板里“构造”对象；只要 `template_vars` 里出现可用对象，就能通过属性链 + 无参方法调用把能力串起来。

## What Changes

- **BREAKING**：为 YAML 预编译引入默认启用的 sandbox 语义（安全默认值）
  - 默认禁止 `()` 无参方法调用（即模板表达式中的 `x.y()` 语法不再执行）
  - 默认禁止访问以下划线开头的属性（包括 `__dunder__`），避免对象自省链路被滥用
  - 保留对 dict/list/tuple 的 key/index 访问能力（满足绝大多数模板替换需求）
- 提供显式的“信任模式”开关（避免过度限制可信场景的高级用法）
  - 仅当调用方显式 opt-in 时，才恢复当前的“属性访问 + 无参方法调用”能力
  - opt-in 时必须给出强提示（日志 warning + 可选诊断事件），以避免生产误用
- 加强 `template_vars` 的输入护栏（降低误注入风险）
  - 递归校验/净化：默认仅允许 YAML/JSON 标量与容器（`None/bool/int/float/str/list/tuple/dict`）
  - 对“非安全类型”的处理策略需要明确（建议默认 fail-fast；也可选 `str()` 降级，但必须在规范中写清副作用与可预期性）
- 增加安全回归测试
  - 默认 sandbox 下，`{{ p.open().read() }}` / `{{ p.unlink() }}` / `{{ obj.__class__ }}` 必须失败或渲染为 undefined（按 LiteJinja2 strict-undefined 语义应 fail-fast）
  - 常见替换用法（dict key、list index、简单变量）必须保持可用

## Capabilities

### New Capabilities
- `yaml-template-vars-sandbox`: 定义 YAML 模板预编译的 sandbox 策略（允许的表达式子集、默认值、以及显式 opt-in 的“信任模式”约束与警告要求）。

### Modified Capabilities
- `yaml-template-vars-precompile`: 补充/收敛现有模板预编译能力的安全边界：默认 sandbox、禁止方法调用与下划线属性访问、以及 `template_vars` 的安全类型约束与错误语义。

## Impact

- 受影响代码路径：
  - `src/scalim/dsl/by_yaml/config_parsing/template_precompile.py`（入口）
  - `src/scalim/vendor/litejinja2/__init__.py`（变量解析/执行语义，需要增加 sandbox 或安全策略分支）
  - 所有通过 `template_vars` 触发预编译的入口（demand/workflow + imports fragments）
- 可能影响既有用法：
  - 若用户依赖 `{{ x.y() }}` 或访问对象属性（尤其是 `_`/`__` 属性），默认行为将变为 fail-fast；可信场景需显式开启信任模式，或将复杂对象提前在调用方转为纯字符串/结构化字典再注入
- 安全收益：
  - 将 YAML “模板渲染”从“可执行副作用”收敛为“受控的文本替换”，显著降低半可信输入下的泄露/破坏风险，并减少误配置导致的安全失效面
