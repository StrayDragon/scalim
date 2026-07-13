# Validate And Debug

## 何时读取

- 用户要“校验 YAML”
- 用户要“订正报错”
- 用户要配置编辑器补全或 schema header
- 你需要明确说明“已验证什么 / 未验证什么”

## 推荐顺序

### 仓库内

```bash
uv run scalim-cli yaml-dsl schema validate <file.yaml>
uv run scalim-cli yaml-dsl validate <file.yaml>
```

### 仓库外

```bash
uvx scalim-cli yaml-dsl schema validate <file.yaml>
uvx scalim-cli yaml-dsl validate <file.yaml>
```

### 查询 schema 路径

```bash
uv run scalim-cli yaml-dsl schema path
uvx scalim-cli yaml-dsl schema path
```

## `schema validate` 与 `validate` 的分工

- `schema validate`
  - 检查 JSON Schema 结构
  - 检查 unknown fields(默认 strict: unknown field 直接作为 error)
  - 更适合快速收敛字段名、结构、枚举和类型
- `validate`
  - 检查运行时语义
  - 会尽可能执行 JSONSchema 校验作为补充(缺依赖/非预期失败时给 warning,但不影响内部语义校验)
  - 更适合抓 relation 链路、派生字段、输出字段歧义、旧写法限制

不要只跑其中一个。

## LSP / 编辑器

我们默认同时写入 Red Hat YAML Language Server 与 JetBrains/IntelliJ 都能识别的 schema modeline,格式如下:

```yaml
# yaml-language-server: $schema=<urlOrPathToTheSchema>
# $schema: <urlOrPathToTheSchema>
```

如果你在本仓库里工作,推荐这条最省事的链路:

```bash
uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>
```

完整 canonical example 故意不自带这个头,避免把 `.venv/...`、`site-packages/...` 或仓库私有相对路径固化进共享 YAML。
如果当前文件就在你自己的仓库里,也可以本地临时使用 repo-relative 路径; 但这只在当前工作树布局下可靠,不适合作为共享示例。

## 高频错误与修复动作

### `Unknown field`

- 先检查拼写
- 再检查是不是旧字段名
- 默认就是 strict(未知字段直接是 error);不需要额外参数

### `Legacy field 'xxx' is not allowed`

- 按 [task-upgrade-legacy.md](task-upgrade-legacy.md) 直接改到新结构

### `write_defaults was removed` / `budget was removed`

症状: YAML books 仍写 `write_defaults` 或 `budget`(含旧 `xlsx_memory.budget` / 新 `xlsx.budget`)。

修复: 删除 YAML 字段；改用 Python `ResourcesPolicy`。book identity 推荐 `xlsx` — 见 `references/upgrades/2026-07-12-book-write-policy-python-ssot.md` 与 `references/upgrades/2026-07-13-unified-xlsx-book-kind.md`。

- book 写入策略与内存预算已迁出 YAML
- 删除 YAML 字段后,在 `DemandRunOptions.resources_policy` / `WorkflowRunOptions.resources_policy` 配置
- SSOT: [upgrades/2026-07-12-book-write-policy-python-ssot.md](upgrades/2026-07-12-book-write-policy-python-ssot.md)
- workflow 场景更多排错见 [task-workflow-validate-debug.md](task-workflow-validate-debug.md)

### `Legacy YAML syntax is not supported: top-level 'output'. ...`

- 顶层 `output:` 已移除;必须升级为 `outputs:`(list)
- 把输出参数移到 `resources.files.*` + `outputs.*.to/write`,把输出字段移到 `outputs.*.fields`
- 参考: [task-upgrade-legacy.md](task-upgrade-legacy.md) / `references/upgrades/`(按批次阅读迁移说明)

### `Field 'xxx' is defined multiple times; field_id must be unique ...`

- `field_id` 必须全局唯一: 不再允许通过输出层做消歧
- 处理方式:
  1) 先在字段定义处重命名(例如 `customer_name` → `customer_name_customer`)
  2) 再在 `outputs.*.fields` 引用新的 `field_id`

### `Legacy \`$runtime.<name>\` placeholder is not supported; use \`{$init_var: <name>}\``

- 把所有 `$runtime.xxx` 替换为 `{$init_var: xxx}`
- 初始化变量由 Python 调用方传入 `init_vars={...}`; YAML 里只声明引用

### relation 相关错误

- 确认 `from` / `to` 使用的是 `source.field_id`(或 list),不要写 loader 的 `data_key`
- 确认 relation 链路连续
- 确认 `sources.<id>.key` 与 step 右侧匹配
- 若出现“本应命中但 miss / 分组拆分”,且确认是 key 类型不一致(例如 `1` vs `"1"`),优先按下面顺序处理:
  - 显式口径: 在 step 上配置 `lookup_cast`,或在 `sources.<id>.key.cast` 统一 key 类型
  - 全局口径(EXPERIMENTAL): 在调用侧启用 `key_normalization="auto_str"`(仅在无显式 cast 时生效)或 `key_normalization="force_str"`(最终匹配边界强制字符串口径)

### `normalize` 相关错误

- `main_source.normalize`:
  - `normalize` 只允许出现在 lookup `sources.*`,不允许写在 `main_source`
- `normalize.key_field is required` / `normalize.key_field must be a non-empty string`:
  - 补齐 `sources.<id>.normalize.key_field`
- duplicate key 报错:
  - 默认 `on_conflict: error` 会 fail-fast
  - 如业务允许覆盖,显式设为 `on_conflict: first|last`
- `normalize` 与 `extract` 的边界:
  - whole-result reshape(例如 `list[row] -> key -> row`)用 `sources.<id>.normalize`
  - 从单条 row 里取嵌套字段用字段级 `extract`

### `call_by` / `loader` 相关错误

- YAML 中只写引用
- allowlist 是运行时参数,不是 YAML 字段
- 如果是外部环境,确认调用侧传入 `allowed_modules` 或 `allowed_functions`

### Excel 输出问题

- `format: excel` 需要 `openpyxl`
- 缺依赖时要明确指出“YAML 已校验,运行依赖未满足”
- 用户抱怨宽表 Excel **峰值 RSS** 时:先读 `references/streaming-column-excel-guidance.md` 与站点 `docs/doc/getting-started/excel-column-residency.md`
  - YAML books 路径已是 **行 sink**,不能靠 YAML 开关切到 `WINDOW`
  - 仅 Python IR 列式(`streaming=False`)才建议 `ExcelColumnResidency.WINDOW`（或手写 `StreamingColumnExcelSink`）

## 交付时必须写清楚

- 已跑哪些命令
- schema header 是否已校正
- 是否缺 `jsonschema`、`openpyxl`、真实数据库、下游服务或 allowlist 上下文
- 静态校验已过,还是仅完成了 schema 校验,还是两者都过

## 一个最小交付模板

- 已完成 `schema validate`
- 已完成 `validate`
- 未完成真实运行验证,因为缺少 `...`
- 当前结论仅覆盖 YAML 结构与语义校验,不覆盖真实数据结果正确性

## 模板预编译(可选): `template_vars`

如果你的 YAML 里出现 `{{ ... }}` / `{% ... %}`:

- 这是 **调用侧** 的编译期开关(例如 `run/compile(..., options=DemandRunOptions(..., template=DemandRunTemplateOptions(template_vars=...)))`),不属于 YAML schema 字段。
- `scalim-cli yaml-dsl schema validate/validate` 当前不暴露 `template_vars` 注入;直接对含模板语法的 YAML 跑 CLI 校验,通常会在 YAML parse 阶段失败。

推荐做法:

- 优先使用 schema 内的结构化注入: `init_vars` + `{$init_var: <name>}`(CLI 可直接校验;也更稳定/可维护)。
- 只有确实需要模板语法时,才在 Python 入口启用 `template_vars`,并在该入口内完成渲染后的 parse + 校验/编译。

排错提示:

- strict-undefined: 缺失变量会 fail-fast;用 `| default(...)` 显式兜底。
- imports 片段也会按同一份 `template_vars` 渲染;缺失变量/渲染失败时,错误信息通常会包含 fragment 路径(import trace)。

需要完整 CLI 说明时再读:

- [generated/cli-lsp-reference.gen.md](generated/cli-lsp-reference.gen.md)
