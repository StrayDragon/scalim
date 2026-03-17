# 2026-03-13: yaml-reuse-workflow

## 变更摘要

本批次聚焦 YAML DSL 的“复用与编排”能力:

- demand YAML 新增跨文件复用: 顶层 `imports` + 任意 mapping 内 `$import`(编译期展开)
- 新增 workflow YAML + Python 入口 `scalim.dsl.by_yaml.run_workflow(...)` 编排多个 demand
- workflow 可选启用 `cache_pool`: 跨 nodes 共享 `cache_mode: preload_forever` 的预加载结果,并通过 signature + 冲突策略治理复用边界（`share_preload_cache` 已移除）

OpenSpec 归档变更（含 proposal/design/spec/tasks）:
- `openspec/changes/archive/2026-03-13-yaml-dsl-imports/`
- `openspec/changes/archive/2026-03-13-yaml-dsl-workflow/`

对应主规范(节选):
- `openspec/specs/yaml-dsl-imports/spec.md`
- `openspec/specs/yaml-dsl-workflow/spec.md`
- `openspec/specs/yaml-dsl-schema/spec.md`
- `openspec/specs/yaml-dsl-cli-validation/spec.md`
- `openspec/specs/yaml-dsl-editor-core/spec.md`
- `openspec/specs/source-cache/spec.md`

下游同步盘点:
- 仅用于盘点与行动: `.tmp/known-outer-paths-using-this-package.txt`（请勿在公开输出中复述其内容）

## demand YAML: `imports/$import`

### 语法要点

- 顶层新增 `imports: {<alias>: <fragment.yaml>}`
- 任意 mapping 节点内允许 `$import`(string 或 string list):
  - `$import: common.sources`
  - `$import: [common.sources, other.sources]`
- V1 路径限制: `imports.*` 仅允许同级文件名: `x.yaml|x.yml` 或 `./x.yaml|./x.yml`
- 展开时机: **先展开 imports,再做 schema/语义校验**
- **仅文件路径入口支持**: `run/compile(yaml_path=...)` 与 CLI validate 会先展开再校验;纯文本入口检测到 `imports/$import` 会 fail-fast 并提示改用文件路径入口

### BREAKING: 保留字冲突

- `$import` 是保留字: 任意 mapping 内出现 `$import` 都会触发 import 语义,不提供转义/兼容模式
- `imports` 是保留字: 顶层 `imports` 仅用于 import alias 映射

若业务配置曾把 `$import`/`imports` 当作普通 key,需要改名后再升级.

## workflow YAML: runs 编排与共享 preload cache

### 最小结构

```yaml
workflow:
  runs:
    - id: a
      demand: ./a.yaml
    - id: b
      demand: ./b.yaml
  options:
    max_concurrency: 2
    failure_policy: primary_only
    cache_pool:
      conflict_policy: error
      release_policy: dag_refcount
      budget:
        max_entries: 16
        over_budget_policy: fail_fast
```

### 失败策略

- `all_fail`: 任一 run 失败即抛出异常(包含 run id 与 demand 路径)
- `primary_only`: 跳过失败 run 继续执行,返回值 `outcomes` 可检查 `error`

### `cache_pool` 约束

- 仅对 `cache_mode: preload_forever` 生效
- cache pool 以“可复现的 signature”作为缓存 key,并支持冲突策略:
  - 同一逻辑 key(同 kind+source_id)出现多个不同 signature 时,`conflict_policy=error` 会 fail-fast
  - `conflict_policy=separate|warn` 允许并行存在多个 entries(互不复用),并发出可观测告警(含差异摘要)
- signature 以 **已渲染的 params** 为准(含 `{$init_var: ...}`),并纳入 normalize/key/lookup_cast 等关键字段

## Migration Checklist

1) (可选) 将重复的 mapping 片段抽到同级 fragment YAML,在主文件用 `imports/$import` 复用
2) 确保所有使用 `imports/$import` 的场景都走“文件路径入口”(不要走纯文本入口)
3) 需要多 demand 编排时,新增 workflow YAML 并从 Python 调用 `run_workflow(...)`
4) 若启用 `workflow.options.cache_pool`,确保同一逻辑 key 下的 signature 边界符合预期（必要时用 `conflict_policy=separate|warn` 作为迁移窗口）
5) 注意: `workflow.options.share_preload_cache` 已移除,请升级到 `cache_pool`
