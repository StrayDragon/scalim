# 2026-03-13: yaml-reuse-workflow

## 变更摘要

本批次聚焦 YAML DSL 的“复用与编排”能力:

- demand YAML 新增跨文件复用: 顶层 `imports` + 任意 mapping 内 `$import`(编译期展开)
- 新增 workflow YAML + Python 入口 `scalim.dsl.by_yaml.run_workflow(...)` 编排多个 demand
- workflow 可选启用 `share_preload_cache`: 跨 runs 共享 `cache_mode: preload_forever` 的预加载结果,并在启动前做规格冲突预检查

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
    share_preload_cache: true
```

### 失败策略

- `all_fail`: 任一 run 失败即抛出异常(包含 run id 与 demand 路径)
- `primary_only`: 跳过失败 run 继续执行,返回值 `outcomes` 可检查 `error`

### `share_preload_cache` 约束

- 仅对 `cache_mode: preload_forever` 生效
- 启动前会按 `source_id` 做规格签名一致性预检查:
  - loader/params/normalize/key/lookup_cast 等关键字段不一致 → fail-fast 报错(包含冲突 run id 与差异点)
  - params 渲染结果若包含不可稳定签名的非字面量对象 → fail-fast

## Migration Checklist

1) (可选) 将重复的 mapping 片段抽到同级 fragment YAML,在主文件用 `imports/$import` 复用
2) 确保所有使用 `imports/$import` 的场景都走“文件路径入口”(不要走纯文本入口)
3) 需要多 demand 编排时,新增 workflow YAML 并从 Python 调用 `run_workflow(...)`
4) 若启用 `share_preload_cache=true`,确保同一 `source_id` 的 preload 规格在所有 runs 中一致
