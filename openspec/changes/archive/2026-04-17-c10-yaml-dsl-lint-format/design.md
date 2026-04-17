## Goals

- 提供类似 ruff 的一组 **YAML DSL authoring 工具**:
  - `scalim-cli yaml-dsl lint`: 发现“可读性/一致性/易踩坑”的问题（风格层）,并能在安全边界内自动修复。
  - `scalim-cli yaml-dsl format`: 幂等地把 YAML 规范到团队推荐风格,重点解决 `loader/call_by/compute` 的引号噪音。
- 让“可读的 multiline `call_by`”不再牺牲 editor 体验:
  - core 解析支持在 `call_by` 参数内写 Python 风格 `#` 注释（尤其是 block scalar 多行）。
  - LSP 支持在 block scalar 中完成 `loader/call_by` 的跳转/hover/补全（至少 head ref 与 kwargs RHS token）。
- 确保对 repo 治理友好:
  - 不手改任何 `*.gen.*` 或注入区块；
  - 通过工具/生成链路更新示例与 skill 产物,保持一致性与可回放。

## Non-goals

- 不引入 “DSL 版本号/并行 parser”（遵循 mainline 原则）。
- 不把 `lint/format` 变成语义校验替代品（语义校验仍由 `yaml-dsl validate`/LSP diagnostics 负责）。
- 第一阶段不做“自动把任意 `call_by` 重排为多行函数签名”的激进重写（可作为后续增强）。

## CLI Design (`scalim-cli yaml-dsl lint/format`)

### Commands

- `scalim-cli yaml-dsl lint <paths...>`
  - 行为: 递归扫描 YAML 文件（支持文件/目录输入）,对每个文件输出按规则归类的 diagnostics。
  - 退出码:
    - `0`: 无 lint 问题
    - `1`: 有 lint 问题（或 `--fix` 部分无法自动修复）
    - `2`: 参数错误/运行时异常
  - 选项建议:
    - `--fix`: 对标 ruff 的 “safe fixes only”
    - `--unsafe-fix`:（可选）允许更激进的风格重写（初期可不实现）
    - `--json`: 机器可消费输出（用于 CI / editor integration）

- `scalim-cli yaml-dsl format <paths...>`
  - 行为: 对 YAML 做 round-trip 解析与重写,只修改风格相关部分,其余保持最大化稳定。
  - 退出码:
    - `0`: 已格式化或无改动
    - `1`: `--check` 模式下发现将产生改动
    - `2`: 参数错误/运行时异常
  - 选项建议:
    - `--check`: 仅检查是否需要改动（CI 友好）
    - `--diff`: 输出 unified diff（便于 review）

### File Discovery

- 规则: 只处理 `.yaml` / `.yml`。
- 递归策略: 目录输入时递归；排除 `.tmp/` 与 `dist/`（遵循 repo 约定,且避免误格式化生成/缓存产物）。

### Formatting rules (v1)

聚焦本次诉求,仅对以下 key 的 **string value** 执行风格归一:

- `loader`
- `call_by`
- `compute`
- `retry.should_retry`（与 callable 引用同一类风险,可一并统一风格）

目标输出偏好:

- “能 plain 就 plain”：例如 `compute: order_id`、`call_by: ..loaders:fn(a=a)`、`loader: mypkg.mod:load_x`。
- “不牺牲语义”：任何会让 YAML 把 string 解释成 bool/null/number 的值必须保留引号（例如 `"false"`、`"null"`、`"1"`）。
- “不破坏可注释的 multiline call_by”：block scalar 的值保持 block scalar；format 不强行折叠/改成单行。

#### Safe plain-scalar decision

不依赖脆弱的正则硬编码,采用“最小 round-trip 门禁”来判断是否可以去引号:

1) 对候选 string `s` 构造最小 YAML 文本: `x: <rendered as plain scalar>`  
2) 用 repo vendored `ruamel.yaml` 的 `YAML(typ="safe", version=(1,2))` 解析  
3) 若解析结果 `x` 的值仍为 **同一个 string `s`**（不是 bool/int/None 等）,则允许输出为 plain scalar；否则保持引号。

该门禁天然覆盖:
- YAML 隐式类型陷阱（true/false/null/123）
- `:` + space 等语法歧义
- 需要引号才能保留的边界（例如 leading/trailing whitespace）

实现策略:
- `format` 使用 `YAML(typ="rt")` 做 round-trip,以保留 comments/anchors/order。
- 对节点值的 style 调整使用 ruamel 的 scalar string 类型（例如从 quoted scalar 转为 plain scalar）,并在 dump 时配置 `preserve_quotes=True` 以保护“必须保留引号”的值。

### Lint rules (v1)

lint 规则建议拆成稳定 code,便于 CI 忽略/分级:

- `YDL001 quoted-reference-can-be-plain`: `loader/call_by/compute` 为 quoted string,且通过 safe-plain 门禁 → 建议去引号（`--fix` 可自动修复）。
- `YDL002 plain-scalar-looks-typed`: 发现 unquoted scalar 在 YAML 解析后不是 string（例如 bool/null/number）但 schema 期望 string → 建议加引号或改写（此类通常也会触发 `validate` 错误,lint 作为更早提示）。
- `YDL003 call-by-multiline-comment-trap`: `call_by` 为 multiline,且包含 `#` 注释,但 core 解析尚未支持（本变更实现后该规则可退化为提示/不报错）。
- `YDL004 long-call-by-suggest-block-scalar`: `call_by` 单行过长（阈值可配置）,建议改为 `|` 以便编辑（不自动修复,避免激进重排）。

## Runtime: `call_by` parser supports Python `#` comments

目标: 允许用户在 `call_by` 的参数段内使用 Python 风格注释,例如:

```yaml
call_by: |
  ..loaders:xx(
    a=a,
    t=t, # trailing comma optional
  )
```

### Current failure modes (root causes)

- `call_by` 解析当前把 args 文本拼进一行 `__scalim_call__(<args>)`。当 args 最后一行存在 `# comment` 时,拼接的 `)` 会被注释吞掉,导致 `SyntaxError: '(' was never closed`。
- `_find_matching_paren` 不理解 `#` 注释语义；当注释中包含 `)` 时可能“提前匹配闭括号”,触发 `unexpected trailing content`。

### Proposed parsing adjustments

- **把闭括号放到新行**：将 call_src 改为:
  - `__scalim_call__(\n{args}\n)`  
  这样 `)` 不会被上一行的注释吞掉。
- **括号匹配忽略注释**：在 `_find_matching_paren` 扫描时,当不在 string 且遇到 `#` 时跳过直到行尾（`\n`）。
- **允许尾随注释**：`_split_reference_and_args` 在检查 close paren 后的 trailing content 时,允许仅包含 whitespace 与 `# ...` 注释。

### Tests

增加覆盖:
- multiline args + inline `#` comment（含尾逗号/无尾逗号）
- comment 中含 `)` 的场景
- close paren 行尾 `)  # comment` 场景

## LSP: block scalar `loader/call_by` navigation

### Scope (v1)

让以下字段在 block scalar 下仍可:
- head reference 的 definition/hover/completion（`loader` / `call_by`）
- `call_by` kwargs RHS field-id 的 definition/hover/completion（已有单行能力,扩展到 multiline）

### Cursor extraction strategy

约束: 现有实现大量依赖单行 range（例如 `_position_in_range` 假设 start/end 在同一行）。因此 v1 采取“**返回 token 所在行的精确 range**”策略,避免重写 server 的 range 语义。

#### Head reference extraction (block scalar)

当遇到 scalar node 跨行时:

1) 通过文本扫描在 `yaml_text` 中定位 block scalar header 行: `(<indent>) (loader|call_by): (| or > variants)`  
2) 识别 block content 的起始行与 content indent  
3) 仅在 cursor 所在行属于 block content 时生效:
   - 取该行去掉 content indent 后的文本片段
   - 对 `call_by` 提取 `(` 之前的 head ref；对 `loader` 提取整行 trimmed
   - 将提取到的 token 映射回原 YAML 行的 column range（`content_indent + offset`）

这样无需构造跨行 EditorRange,也能满足 definition/hover/completion 的“可跳转 item”诉求。

#### kwargs RHS field-id extraction (block scalar `call_by`)

复用现有单行 `call_by kwargs value` tokenizer（它本身已支持括号/引号/嵌套与换行字符）,关键是获得 `cursor_offset`:

- 以 block content 的第一行作为 value 的第 1 行,将 YAML 行号映射为 value 内行号；
- `cursor_offset = sum(len(line_i)+1 for i < rel_line) + rel_col`（`rel_col` 为 `cursor_col0 - content_indent`）；
- 以 scalar 的整体 `reference_raw`（拼接 block content,保留 `\n`）作为 tokenizer 输入；
- 最终得到 token 在 value 内的 start/end offset 后,再反向映射回 YAML 的 line/column range（仅覆盖 token 所在行）。

### Degrade gracefully

沿用既有约束:
- YAML parse 失败时返回空结果 + warnings（不得 crash）
- partially-valid YAML 允许 fallback（参考现有 `$import` 的 line-based fallback）

## Docs / Skills alignment

### Source-of-truth

- canonical full example SSOT: `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`
- skill 生成入口: `scripts/gen-agent-skill.py`
- 禁止手改生成物: `agentdev/skills/scalim-yaml-dsl/references/*.gen.*` 与 `agentdev/skills/scalim-yaml-dsl/references/generated/**`

### Update strategy

- 在实现落地后:
  1) 先对 SSOT YAML 运行 `scalim-cli yaml-dsl format`
  2) 再运行 `python scripts/gen-agent-skill.py` 更新受控产物
  3) 最后 `just gen-docs` 刷新注入区块与 docs-site 页面

## Rollout / Compatibility

- 新增 CLI 命令为向后兼容扩展；format 默认仅做 safe changes。
- runtime `call_by` 解析扩展为 additive；不改变既有无注释写法。
- LSP multiline 支持为 additive；旧 client 不受影响,升级 `scalim-yaml-dsl-lsp` 即可获得。

