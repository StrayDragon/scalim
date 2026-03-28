## Context

当前 YAML DSL 在多个入口存在“同类功能的不同实现”：
- CLI validate / schema validate
- `compile/run`（demand 路径）
- workflow config load/validate（workflow 路径）
- imports fragments（间接加载）

这些实现各自处理了重复 key、location/定位、错误消息格式、默认值/枚举校验等，但缺少统一 facade，导致行为漂移与维护成本上升。

约束：
- `src/scalim/` 运行时保持 Python 3.6 兼容。
- schema 生成与 editor 分发属于 SSOT 链路的一部分，必须可 drift gate。

## Goals / Non-Goals

**Goals:**
- 让“YAML load + location + error envelope”成为单点能力：所有入口复用，保证一致性。
- 让“schema_dsl 枚举/默认值”成为单点 SSOT：validator/parser 只引用不复制。
- 让 CLI/compile/workflow validate 的错误结构一致（可被上层工具消费，且可定位到文件/行列）。

**Non-Goals:**
- 不在本 change 内重写 DSL 语义或引入新的大语法（重点是严谨性与一致性）。
- 不在本 change 内解决所有安全治理（trusted/unsafe/模板上限由其它 change 处理）。

## Decisions

### 1) 引入统一的 YAML load facade（带 location 与错误 envelope）

决策：
- 新增一个单点模块（示意：`src/scalim/dsl/by_yaml/config_parsing/yaml_load.py`），对外提供：
  - `load_yaml_text(text, *, source_path, detect_duplicate_keys=True, ...) -> (mapping, location_index)`
  - `load_yaml_file(path, ...)`
- facade 负责：
  - duplicate key 检测（同一策略用于 demand/workflow/fragment）
  - location index 构建（同一结构用于 CLI 与 runtime）
  - 统一抛出/返回结构化错误（见 Decision 2）

理由：
- 将“文本解析层”从“语义校验层”解耦，减少调用方重复实现。
- 单点可让测试覆盖更集中，并降低 drift 风险。

### 2) 统一错误结构（可机器消费的 ErrorEnvelope）

决策：
- 引入稳定的错误 envelope（dataclass 或 TypedDict，Python 3.6 兼容），字段至少包含：
  - `code`（短码，便于归类）
  - `message`（用户可读）
  - `source_path`（文件路径/逻辑来源）
  - `loc`（行/列/范围，若可得）
  - `path`（YAML 路径，若可得）
- CLI `--json` 与 workflow validate 输出复用同一 envelope。

理由：
- 同一错误在不同入口格式一致，利于 editor/工具链消费。
- 便于后续做错误去敏/安全消息（与 `safe_error_message` 一致化）。

### 3) schema_dsl 作为枚举/默认值的单点 SSOT，并加一致性自检

决策：
- 将枚举/默认值/描述文本收敛在 `schema_dsl`（或其子模块）导出。
- validator/parser 禁止复制同一份 enum/默认值；只能引用。
- 增加一个一致性自检（测试或脚本）：schema 里允许的 enum == runtime 接受的 enum（至少覆盖核心字段）。

理由：
- 避免“改 schema 忘了改 runtime”的双写漂移。

### 4) schema 分发：单点生成 + 可审计复制

决策：
- 明确一个 canonical schema 输出位置（Python 侧）。
- editor 侧 schema 只允许从 canonical 位置复制/打包（通过单一脚本入口），并用 drift gate 覆盖。

理由：
- 减少多份拷贝路径带来的同步成本与回归风险。

## Risks / Trade-offs

- [迁移成本] 调用方入口多：→ 分阶段替换（先 CLI 与 workflow validate，再 compile/run），并用一致性测试兜底。
- [错误兼容] 统一 error envelope 可能影响既有 CLI 文本输出：→ 保留文本输出，但 JSON 输出结构先稳定；文本可在后续迭代对齐。
- [定位精度] location index 可能在部分 YAML 特性下不完美：→ 先覆盖主路径（mapping/sequence/scalar），对极端特性降级为“尽力定位”。

## Migration Plan

- 阶段 1：落地 `yaml_load` facade + ErrorEnvelope，并在 CLI validate 中首先使用（最可控）。
- 阶段 2：workflow validate/compile/run 迁移到同一 facade，并补充“同 YAML 报错一致性”回归。
- 阶段 3：收敛 constants/enum 来源并加入一致性自检；统一 schema 分发脚本入口与 drift gate。

## Open Questions

- location index 结构是否需要与 editor（Monaco/YAML AST）对齐，以便未来跨端复用？
- ErrorEnvelope 的 `code` 是否需要对齐既有 error taxonomy（`openspec/specs/error-taxonomy`）？

