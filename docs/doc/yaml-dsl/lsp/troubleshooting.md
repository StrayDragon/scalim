# Troubleshooting（YAML DSL LSP）

这页提供一个最小排障 checklist,用于处理“server 启动了但 diagnostics/跳转不工作”等问题。

## 1) 先拿到 discovery 摘要（最重要）

推荐把下面命令的输出粘贴到 issue/群聊里（避免靠猜）：

```bash
uvx scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json
# installed: scalim-yaml-dsl-lsp dump-discovery path/to/demo.yaml --json
```

你需要重点检查：

- `project_root` 是否为你预期的项目根
- `scalim_yaml_path` 是否指向预期的那份 `scalim.yaml`（nearest-wins）
- `python_roots` 是否包含你的代码根（例如 `src`）
- `allowed_yaml_roots` 是否覆盖 imports 需要读取的目录

## 2) 常见问题与修复

### 2.1 `scalim.yaml` 缺失

现象：

- diagnostics 提示 project discovery 失败或 roots 缺失
- imports/跳转行为不稳定（因为默认 `project_root` 退化为入口 YAML 所在目录）

处理：

- 在 `project_root` 下创建 `scalim.yaml`（或使用支持 code actions 的 client 触发 “Create minimal scalim.yaml”）

最小示例：

```yaml
yaml_dsl:
  import_roots:
    - path: .
      alias: "@"
  lsp:
    python_roots:
      - src
```

### 2.2 imports 报 allowed roots 越界

现象：

- diagnostics 中出现 “YAML path escapes allowed roots” 类错误

处理：

- 优先使用 code action 一键补全：
  - 最小修复：补充单个缺失目录到 `yaml_dsl.import_roots`（添加 `- {path: <dir>}`）
  - 宽松修复：将 `.` 加入 `yaml_dsl.import_roots`（添加 `- {path: .}`）
- 或手工编辑 `scalim.yaml` 对齐 `allowed_yaml_roots`

### 2.3 Python 引用跳转不工作（definition/hover/completion）

现象：

- `loader`/`call_by` 引用无法解析
- hover 为空或没有候选补全

处理：

- 检查 `python_roots` 是否覆盖你的模块根（常见为 `src`）
- 确认引用语法为 `module:attr` 或 `module.attr`
- 若 client 支持 code actions,可尝试：
  - “Add yaml_dsl.lsp.python_roots”（最小/宽松）
  - “Explain resolution failure”（仅解释,不改写引用字符串）

## 3) 日志获取

server 日志默认输出到 stderr。为避免编辑器吞日志,推荐直接落盘：

```bash
uvx scalim-yaml-dsl-lsp serve --log-level DEBUG --log-file /tmp/scalim-yaml-dsl-lsp.log
# installed: scalim-yaml-dsl-lsp serve --log-level DEBUG --log-file /tmp/scalim-yaml-dsl-lsp.log
```

## 4) Schema 与 LSP 的协作边界（避免误判）

- schema 插件负责结构校验/补全（`$schema` / settings 绑定）
- YAML DSL LSP 负责语义 diagnostics + Python 引用跳转/hover/补全（以及 actions）

当你看到“结构字段缺失/类型不对”这类错误,优先看 schema 插件；当你看到“imports 越界 / Python 引用不可解析”这类错误,优先看 YAML DSL LSP。
