## Context

当前 `scalim.yaml` 的 imports 配置由两个字段共同承担:

- `yaml_dsl.import_aliases`: 为 `imports.*` 提供目录别名,用于把 `alias:/...` / `@/...` 重写成某个 base dir。
- `yaml_dsl.import_allowed_roots`: 用于限制/扩展 imports 解析后的 fragment 文件必须位于哪些 roots 内。

现实项目中,alias 与 roots 往往指向同一批目录,并且实现层面存在 “allowed roots” 的二次校验,导致用户必须重复写目录才能通过校验,非常容易误解与踩坑。

同时,`allowed_yaml_roots` 在 runtime/CLI/LSP 侧都有入口,容易出现漂移(例如 CLI 默认传入空列表导致 project config 被忽略)。

## Goals / Non-Goals

**Goals:**
- 将 `scalim.yaml` 中与 imports 相关的目录配置收敛为单一入口,消除重复声明。
- 允许在同一结构中表达“目录注册”与“可选 alias”,并以其推导 imports 的默认 allow-roots。
- 保留调用侧显式 `allowed_yaml_roots` 作为 override/收紧能力,并保证 runtime/LSP/CLI 的解释一致。
- 破坏性变更可接受: 不提供旧字段的兼容层,改为 fail-fast + 清晰迁移指引。

**Non-Goals:**
- 不改变 imports v2 的路径约束(仍仅支持相对 `.yaml/.yml` 与 `scalim://` preset)。
- 不改变 demand `$import` 的作用域边界(仅限既定 scope)。
- 不引入远程 URI/网络 imports。

## Decisions

### 1) 新增 `yaml_dsl.import_roots` 作为单一入口

在 `scalim.yaml` 中引入:

```yaml
yaml_dsl:
  import_roots:
    - path: ./fragments
      alias: fragments
    - path: ./shared_yaml
      alias: shared
```

语义:
- `path` 是一个已存在的目录(相对 `scalim.yaml` 所在目录,必须不越界 project_root)。
- `alias` 可选:
  - 用于 `imports.*` 的 `alias:/...` 前缀重写。
  - 兼容既有的 `@/` 语法: 当 `alias: "@"` 存在时允许 `@/x.yaml`。

约束:
- alias 必须全局唯一(同一 `scalim.yaml` 内)；冲突时 fail-fast,避免不确定解析。

### 2) 移除旧字段（破坏性）

**BREAKING**:
- 移除 `yaml_dsl.import_aliases`
- 移除 `yaml_dsl.import_allowed_roots`

旧字段被视为 unknown keys 并 fail-fast,要求用户迁移到 `import_roots`。

### 3) imports 的 allow-roots 推导规则统一

在 runtime/LSP/CLI 三处保持同一策略:

- 若调用侧显式提供 `allowed_yaml_roots`:
  - 使用调用侧的 roots(并强制包含入口 YAML 所在目录)。
  - 仍会读取 `scalim.yaml` 的 `import_roots` 用于 alias 重写,但不会隐式扩展调用侧 roots。
- 若调用侧未提供 `allowed_yaml_roots`:
  - 默认 allow-roots = `entry_yaml_dir` + `import_roots[*].path`。
  - 这使 imports 在跨目录复用时只需要维护一处 `import_roots`,不再重复写 “allowed roots”。

### 4) CLI validate 默认不再隐式覆盖 project config

将 `scalim-cli yaml-dsl validate` 的 `--allowed-yaml-root` 默认从 “空列表” 调整为 “未提供(None)”:
- 未提供时: 使用 `scalim.yaml` 的默认推导(与 LSP/运行时一致)。
- 提供时: 明确覆盖并收紧/扩展 roots。

### 5) 文档/生成边界与 drift gate

涉及 schema 与 docs/skills 的变更遵循:
- schema SSOT: `src/scalim/dsl/by_yaml/schema_dsl/models/scalim_yaml.py`
- 生成物: `src/scalim/dsl/by_yaml/schema/scalim_yaml.gen.json`（禁止手改）
- 文档与技能同步: 通过 `just gen-docs` / `just gen-agent-skill` 保持一致
- 提交前 `just qa` + `just openspec-check` 兜底 drift

## Risks / Trade-offs

- [破坏性配置变更] → 通过 fail-fast 错误信息 + 文档迁移指南 + LSP code action 辅助迁移缓解。
- [alias/roots 语义变化导致历史项目 imports 失败] → 迁移后 `import_roots` 明确列出跨目录依赖；调用侧显式 `allowed_yaml_roots` 仍可 override。
- [CLI 行为变化] → 变更后 CLI 默认更符合直觉(读取 project config),但需要在 release notes 中强调。

## Migration Plan

1) 将 `scalim.yaml` 中:

```yaml
yaml_dsl:
  import_aliases:
    fragments: ./fragments
  import_allowed_roots:
    - ./fragments
    - ./shared_yaml
```

迁移为:

```yaml
yaml_dsl:
  import_roots:
    - path: ./fragments
      alias: fragments
    - path: ./shared_yaml
```

2) 若有 `@/` 语法依赖,确保存在 `alias: "@"` 的 root:

```yaml
yaml_dsl:
  import_roots:
    - path: .
      alias: "@"
```

3) 更新 docs/skills/schema 生成物:
- `just gen-docs`
- `just gen-agent-skill`
- `just gen-yaml-dsl-schema`（或仓库既定的 schema 生成入口）

4) 运行质量门禁:
- `just qa`
- `just openspec-check`

## Open Questions

- `import_roots` 是否需要支持 mapping shorthand（例如 `{alias: path}`）？本次不做,避免再引入“双口径”。

