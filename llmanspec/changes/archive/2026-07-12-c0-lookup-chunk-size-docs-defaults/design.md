# Design: lookup-chunk-size-docs-defaults

## 决策

1. **运行时默认不变**：`lookup_chunk_size=None/0` = 不分片（单次 loader 调用）。不静默改默认 chunk。
2. **杠杆落在文档 + schema 描述**：作者在有 payload/IN 上限时才设 chunk，并取**最大安全值**；避免“习惯性小 chunk”线性放大 RTT。
3. **与 notplan 边界**：chunk 并行见 `llmanspec/notplan/c0-perf-refloader-chunk-parallelism/`，本 change 不做。

## 证据

- `.tmp/evidence/exec-call-io/`：`loader_calls = ceil(keys/chunk)` 可复现；过小 chunk 放大 wall。
- ROI：文档/配置杠杆优先于实现并行。

## 文档/生成边界

| 工件 | 角色 | 入口 |
|---|---|---|
| `docs/doc/yaml-dsl/user-guide.md` | 手工 SSOT | 直接编辑 |
| `docs/doc/yaml-dsl/capability-matrix.md` | 手工 SSOT | 直接编辑 |
| `src/scalim/dsl/yaml_dsl/schema_dsl/constants.py` | schema 描述 SSOT | 直接编辑 |
| `src/scalim/dsl/yaml_dsl/schema/demand.gen.json` | 生成物 | `just gen-yaml-dsl-schema` |

禁止手改 `*.gen.*`。
