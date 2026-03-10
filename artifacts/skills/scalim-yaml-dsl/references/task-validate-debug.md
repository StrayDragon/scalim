# Validate And Debug

## 何时读取

- 用户要“校验 YAML”
- 用户要“订正报错”
- 用户要配置编辑器补全或 schema header
- 你需要明确说明“已验证什么 / 未验证什么”

## 推荐顺序

### 仓库内

```bash
uv run scalim-cli yaml-dsl schema validate <file.yaml> --strict
uv run scalim-cli yaml-dsl validate <file.yaml> --strict
```

### 仓库外

```bash
uvx --from "scalim[cli]" scalim-cli yaml-dsl schema validate <file.yaml> --strict
uvx --from "scalim[cli]" scalim-cli yaml-dsl validate <file.yaml> --strict
```

### 查询 schema 路径

```bash
uv run scalim-cli yaml-dsl schema path
uvx --from "scalim[cli]" scalim-cli yaml-dsl schema path
```

## `schema validate` 与 `validate` 的分工

- `schema validate`
  - 检查 JSON Schema 结构
  - 检查 unknown fields
  - 更适合快速收敛字段名、结构、枚举和类型
- `validate`
  - 检查运行时语义
  - 更适合抓 relation 链路、派生字段、输出字段歧义、旧写法限制

不要只跑其中一个。

## LSP / 编辑器

优先把 `schema path` 的绝对路径写入头部:

```yaml
# yaml-language-server: $schema=/absolute/path/to/demand.gen.json
```

完整 canonical example 故意不自带这个头,避免把 `.venv/...`、`site-packages/...` 或仓库私有相对路径固化进共享 YAML。
如果当前文件就在你自己的仓库里,也可以本地临时使用 repo-relative 路径; 但这只在当前工作树布局下可靠,不适合作为共享示例。

## 高频错误与修复动作

### `Unknown field`

- 先检查拼写
- 再检查是不是旧字段名
- 需要时加 `--strict` 让问题尽早变成 error

### `Legacy field 'xxx' is not allowed`

- 按 [task-upgrade-legacy.md](task-upgrade-legacy.md) 直接改到新结构

### `output.fields must be explicit field object`

- 把字符串写法改成 alias 或显式对象

### `output.fields is required to disambiguate`

- 有重名字段,需要在 `output.fields` 中显式选择
- 必要时补 `source`

### relation 相关错误

- 确认 `from` / `to` 使用的是 `field_id`
- 确认 relation 链路连续
- 确认 `sources.<id>.key` 与 step 右侧匹配

### `call_by` / `loader` 相关错误

- YAML 中只写引用
- allowlist 是运行时参数,不是 YAML 字段
- 如果是外部环境,确认调用侧传入 `allowed_modules` 或 `allowed_functions`

### Excel 输出问题

- `format: excel` 需要 `openpyxl`
- 缺依赖时要明确指出“YAML 已校验,运行依赖未满足”

## 交付时必须写清楚

- 已跑哪些命令
- 是否用了 `--strict`
- schema header 是否已校正
- 是否缺 `jsonschema`、`openpyxl`、真实数据库、下游服务或 allowlist 上下文
- 静态校验已过,还是仅完成了 schema 校验,还是两者都过

## 一个最小交付模板

- 已完成 `schema validate`
- 已完成 `validate`
- 未完成真实运行验证,因为缺少 `...`
- 当前结论仅覆盖 YAML 结构与语义校验,不覆盖真实数据结果正确性

需要完整 CLI 说明时再读:

- [generated/cli-lsp-reference.gen.md](generated/cli-lsp-reference.gen.md)
