# 配置补全与编辑体验

??? note "适用读者"
    - 写 YAML 配置并希望获得补全/校验的使用方
    - 需要更严格语义校验的开发者

??? note "现状"
    - 仓库内的 Web 编辑器 `frontend/scalim-yaml-dsl-editor/` 已移除(后续计划以 LSP/IDE 集成为主)
    - 当前推荐路径: JSON Schema 补全/校验 + `scalim-cli` 做语义校验

## 项目发现与文件识别

编辑器/LSP 要想提供稳定的跳转与诊断,需要先确定:

- `project root`(项目根)
- `python_roots`(用于静态解析 `loader`/`call_by` 等 Python 引用的搜索根)
- `allowed_yaml_roots`(用于限制 YAML imports 读取范围,避免越界)
- 当前 YAML 属于 `demand` 还是 `workflow`(决定 schema/diagnostics 边界)

当前 SSOT 是项目配置文件 `scalim.yaml`(nearest-wins):

- 从入口 YAML 所在目录向上查找最近的 `scalim.yaml`
- 若未找到,则以入口 YAML 所在目录作为默认 `project root`

### `scalim.yaml` 的 editor 配置

```yaml
# scalim.yaml
yaml_dsl:
  editor:
    # 可选: 用于静态解析 Python 引用的搜索根(相对 scalim.yaml 所在目录)
    python_roots:
      - .
      - ./src

    # 可选: 按文件路径覆盖 YAML 类型(demand/workflow),glob 相对 project root
    kind_overrides:
      - glob: "workflow/*.yaml"
        kind: workflow
```

### 默认启发式(无覆盖时)

- 当 YAML 根 mapping 包含键 `workflow` 且其值为 mapping 时,判定为 `workflow`
- 否则判定为 `demand`

## Schema 补全/校验

YAML DSL / `scalim.yaml` 的 canonical schema 生成物在:

- `src/scalim/dsl/by_yaml/schema/scalim_yaml.gen.json` (`scalim.yaml`)
- `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- `src/scalim/dsl/by_yaml/schema/workflow.gen.json`

刷新生成物:

```bash
just gen-yaml-dsl-schema
```

打印 schema 绝对路径(便于复制到 `$schema` header):

```bash
scalim-cli yaml-dsl schema path --type scalim_yaml
```

在 YAML 文件头使用 IntelliJ 兼容的 schema header(推荐):

```yaml
# scalim.yaml
# $schema: /ABS/PATH/TO/src/scalim/dsl/by_yaml/schema/scalim_yaml.gen.json
```

```yaml
# demand/workflow YAML
# $schema: /ABS/PATH/TO/src/scalim/dsl/by_yaml/schema/workflow.gen.json
```

在 VSCode / `redhat.vscode-yaml` 中通过 settings 绑定 schema(示例):

```json
{
  "yaml.schemas": {
    "/ABS/PATH/TO/src/scalim/dsl/by_yaml/schema/scalim_yaml.gen.json": "scalim.yaml",
    "/ABS/PATH/TO/src/scalim/dsl/by_yaml/schema/demand.gen.json": "demand/**/*.y*ml",
    "/ABS/PATH/TO/src/scalim/dsl/by_yaml/schema/workflow.gen.json": "workflow/**/*.y*ml"
  }
}
```

## 语义校验(命令行)

需要对齐运行时的更严格语义约束时,使用 CLI 校验:

```bash
scalim-cli yaml-dsl validate /path/to/config.yaml
```

## LSP/IDE 集成

本仓库不交付 VSCode 扩展,但会提供:

- `scalim_yaml_dsl_lsp.core` 作为可复用的 editor/tooling 语义层 API(不调用 CLI)
- `scalim-yaml-dsl-lsp serve`：可运行的 YAML DSL LSP server 启动入口（stdio）
- `scalim.yaml` 的 project discovery/kind override 配置口径
- `demand.gen.json` / `workflow.gen.json` schema 资源(供 `redhat.vscode-yaml` 绑定)

多编辑器接入与排障指南见：[YAML DSL LSP/IDE 集成](lsp/index.md)

相关规范(SSOT):

- `openspec/specs/yaml-dsl-editor-project-discovery/spec.md`
- `openspec/specs/yaml-dsl-lsp-serve/spec.md`
- `openspec/specs/yaml-dsl-lsp-server/spec.md`
- `openspec/specs/yaml-dsl-lsp-code-actions/spec.md`
- `openspec/specs/yaml-dsl-vscode-extension/spec.md`
