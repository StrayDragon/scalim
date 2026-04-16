# 2026-04-07: yaml-dsl-import-roots-registry

## 变更摘要

本批次收敛 `scalim.yaml` 中与 YAML imports 相关的 project config,将原先的两处配置入口:

- `yaml_dsl.import_aliases`(路径别名)
- `yaml_dsl.import_allowed_roots`(imports allow roots)

合并为一个“注册表式”的单入口:

- `yaml_dsl.import_roots: [{path: <dir>, alias?: <alias>}, ...]`

其中每个条目同时承担两类职责:

- **默认 allow-roots 扩展输入**: 当调用侧未显式提供 `allowed_yaml_roots` 时,`import_roots[*].path` 会扩展 imports 的默认 allow-roots
- **别名解析基准**: 当条目配置了 `alias` 时,可在 `imports.*` 中使用 `@/x.yaml` 或 `<alias>:/x.yaml`

OpenSpec 归档变更（含 proposal/design/spec/tasks）:
- `openspec/changes/archive/2026-04-07-c41-yaml-dsl-import-roots-registry/`

对应主规范(节选):
- `openspec/specs/yaml-dsl-project-config-schema/spec.md`
- `openspec/specs/yaml-dsl-import-aliases-and-presets/spec.md`
- `openspec/specs/yaml-dsl-editor-project-discovery/spec.md`

## 新语法要点

`scalim.yaml` 中 imports 相关配置现在仅保留:

```yaml
yaml_dsl:
  import_roots:
    - path: ./fragments
      alias: fragments
    - path: ./shared_yaml
```

约束要点:

- `path` 相对 `scalim.yaml` 所在目录；必须为存在的目录,且不可越过 project root
- `alias` 可选；当为 `@` 时允许 `@/x.yaml`; 其他 alias 允许 `<alias>:/x.yaml`
- `alias` 必须唯一

## 迁移方式(旧 → 新)

将旧的两个字段删除,并将每个目录“只写一次”迁移到 `import_roots`:

Before:

```yaml
yaml_dsl:
  import_aliases:
    shared: ./shared_yaml
  import_allowed_roots:
    - .
    - ./shared_yaml
```

After:

```yaml
yaml_dsl:
  import_roots:
    - path: .
      alias: "@"
    - path: ./shared_yaml
      alias: shared
```

## 注意事项

- 当调用侧显式提供 `allowed_yaml_roots`(例如 Python API 的 `DemandRunSecurityOptions(allowed_yaml_roots=...)` 或 CLI 的 `--allowed-yaml-root`)时,该值优先生效,`import_roots` 不会隐式扩展它。
- 当调用侧未提供 `allowed_yaml_roots` 时,imports 默认 allow-roots 将包含:
  - 入口 YAML 文件所在目录
  - `scalim.yaml` 中 `import_roots[*].path`
