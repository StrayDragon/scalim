# Proposal: lookup-chunk-size-docs-defaults

## Why

`sources.*.lookup_chunk_size` 已在 IR/执行层落地：keys 模式下把一次 LoadRef 拆成多次 loader 调用再合并；`0/None` = 不分片。本地 MVP 证明串行分片是可预测的 IO 放大器：

| 证据 | 路径 | 结论摘要 |
|---|---|---|
| chunk 串行 | `.tmp/evidence-mvp/exec-call-io/20260712T075142Z/result.json` | 300 keys / chunk 40 → **8** loader calls（= ceil）；500/25 → **20** calls |
| ROI 草案 | `.tmp/evidence-mvp/ROI-draft-three-questions.md` | 优先 **文档/配置杠杆**；不要先做 chunk 并行（见 `notplan/c0-perf-refloader-chunk-parallelism`） |
| adaptive 对照 | 同 topic，RTT=50ms 时 dual LoadRef ~1.7–2.1× | adaptive 有价值；与 chunk 串行是正交杠杆 |

当前用户文档缺口：`docs/doc/yaml-dsl/user-guide.md` 几乎不讲 `lookup_chunk_size` 的选用与代价；作者容易把 chunk 设得过小，线性放大 RTT。

## What Changes

1. **文档（SSOT）**：在 `docs/doc/yaml-dsl/user-guide.md`（及必要时 `capability-matrix.md`）写清：
   - 省略 / `0` / `null` = **不分片**（单次 loader 调用；通常延迟最优）
   - 仅在下游有 **payload/IN 长度上限** 时设置
   - 代价：`loader_calls ≈ ceil(unique_keys / chunk_size)`，wall ≈ calls × RTT（seq）
   - 建议起步值（文档推荐，非强制）：按下游限制取最大安全值（例如 SQL IN 上限的 50–80%），避免「习惯性设 50」
2. **默认值杠杆**：
   - **运行时默认保持 `None`（不分片）** — 不改变现有行为
   - 「默认值」指文档推荐默认策略：优先省略；需要分片时用「尽量大」而非「尽量小」
3. **Schema 描述**：若 `DESC_LOOKUP_CHUNK_SIZE` / schema markdown 需同步，走 SSOT → `just gen-docs`（禁止手改 `*.gen.*`）
4. **不在范围**：chunk 并行、改 adaptive 锁、改 loader API

## Capabilities

### Modified Capabilities

- `yaml-dsl-source-lookup-chunk-guidance` — 文档与 schema 描述层面对 `lookup_chunk_size` 的选用语义（待 delta；行为 MUST 与现执行层一致）

## Impact

- **代码区域**: 主要为 docs；可选 `src/scalim/dsl/yaml_dsl/schema_dsl/constants.py` 描述字符串
- **破坏性**: 无运行时行为变更（默认仍不分片）
- **生成物**: 若动 schema 描述 → `just gen-docs` + drift gate
- **相关 notplan**: `llmanspec/notplan/c0-perf-refloader-chunk-parallelism/`（并行另案，本 change 不激活）

## 固定证据脚本

见本 change 内 `evidence-mvp/repro_lookup_chunk_calls.py`（输出落 `.tmp/evidence-mvp/`）。

## Ethics

- `ethics.risk_level`: low
- `ethics.prohibited_actions`: 不在本 change 静默改运行时默认 chunk；不把并行 chunk 混进本 PR

## 进度

- [x] 补 user-guide §4.4.3 + capability-matrix 指引
- [x] 同步 schema DESC → `just gen-yaml-dsl-schema`（`demand.gen.json`）
- [x] delta specs + tasks + validate（运行时默认仍不分片）
- [ ] qa / archive（用户确认后）
