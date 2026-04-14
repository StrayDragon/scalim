## Why

workflow YAML 里 `workflow.runs[*].demand` 以字符串引用 demand YAML 文件；当前 `scalim-yaml-dsl-lsp` 已支持 Python 引用与 `$import` 的 go-to-definition，但对该 demand path 仍无法跳转，导致编写/维护 workflow 时跨文件定位成本较高。

## What Changes

- 为 workflow YAML 的 `workflow.runs[*].demand` 字段新增 go-to-definition：在编辑器中触发时跳转到解析后的 demand YAML 文件（file URI）。
- demand path 解析规则与 runtime 保持一致：
  - 相对路径以 workflow 文件所在目录为基准；
  - 支持 `@/...` 与 `ALIAS:/...` 形式（alias 取自 `scalim.yaml` 的 `yaml_dsl.import_roots[].alias` 作为 editor 侧默认 path_aliases）。
- 失败时必须可诊断降级：解析失败/越界/不存在等场景返回空结果（不得 crash）。

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `yaml-dsl-lsp-server`: 新增 `workflow.runs[*].demand` 的 definition 解析与跳转行为要求。

## Impact

- 代码影响范围：`packages/scalim-yaml-dsl-lsp`（cursor extraction + definition handler）。
- 不涉及 schema/生成物/注入区块的修改；无需触发 `just gen-docs`。
