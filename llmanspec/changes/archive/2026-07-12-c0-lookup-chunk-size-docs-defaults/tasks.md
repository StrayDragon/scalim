# Tasks: lookup-chunk-size-docs-defaults

## 1. 文档与 schema

- [x] 1.1 `docs/doc/yaml-dsl/user-guide.md` §4.4.3
- [x] 1.2 `docs/doc/yaml-dsl/capability-matrix.md` 行更新
- [x] 1.3 `DESC_LOOKUP_CHUNK_SIZE(_MD)` + `just gen-yaml-dsl-schema`
- [x] 1.4 运行时默认保持 `None`（不分片）— 无代码行为变更

## 2. 规范与验收

- [x] 2.1 delta `demand-dsl`（modify r6）
- [x] 2.2 `llman sdd validate c0-lookup-chunk-size-docs-defaults --strict --no-interactive`
- [x] 2.3 `just schema-drift-check`

## 后续（非本 change 阻塞项）

- `just qa` / archive：用户确认后再做
