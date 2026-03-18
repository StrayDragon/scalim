## Context

本次变更聚焦 YAML DSL 校验/诊断链路的可维护性与一致性。

当前(基准)实现存在以下典型问题:

- **schema 校验收敛不足**:
  - 内部校验器 `ConfigValidator` 使用 `jsonschema.validate(...)`，只能产出“第一条” schema 错误；
  - CLI `yaml-dsl schema validate` 使用 `Draft7Validator.iter_errors(...)`，能产出“完整错误列表”；
  - 两者在错误条目数量、排序、message/path 细节上不一致，容易造成下游误判/回归。
- **unknown-fields 依赖与覆盖不稳定**:
  - `yaml-dsl validate` 默认 strict unknown fields，但在无 `jsonschema` 环境下，unknown-fields 的覆盖能力受限（例如 schema 中 `oneOf/anyOf` 分支下的 mapping key 校验可能漏报）。
- **重复诊断**:
  - 当同时启用 schema 校验与 unknown-fields 检查时，可能对同一未知字段产生两条错误（jsonschema additionalProperties + unknown-fields），影响可读性与脚本化消费。
- **`{$init_var: ...}` 结构校验重复**:
  - `outputs.*.container.path` 的 `$init_var` 节点结构校验在 parser/runtime 各写一份；CLI validate 又不走 parser，导致某些形态错误只能靠 schema 校验兜底（依赖 `jsonschema` 是否存在）。

约束:

- `src/scalim/` 运行时代码必须保持 Python 3.6 兼容。
- `jsonschema` 为可选依赖；`yaml-dsl validate` 必须在缺失/异常时仍可用（以 warning 形式提示）。
- 不新增 `--strict` 等额外开关；默认即 strict unknown fields。

**文档/生成边界与 drift gate**

- **SSOT (规范)**: `openspec/specs/yaml-dsl-cli-validation/spec.md`
- **本次变更 delta specs**: `openspec/changes/c2-yaml-dsl-validation-refactor/specs/yaml-dsl-cli-validation/spec.md`
- **生成物/注入区块**: 本次预计不修改 `.gen.` 文档与 injected-block；若后续需要更新 docs，则必须通过 `just gen-docs` 生成，不可手改 `.gen.` 或注入区块内容。
- **验证门禁**: `just test`、`just qa`、`just openspec-check`

## Goals / Non-Goals

**Goals:**

- 在不改变 DSL 语义的前提下，统一并收敛 schema/unknown-fields 诊断逻辑，使 CLI 输出更稳定、更可预测。
- 将 schema issues 收集逻辑抽为可复用实现，并在 `yaml-dsl validate` 与 `yaml-dsl schema validate` 之间共享，减少实现漂移风险。
- 让 strict unknown fields 在无 `jsonschema` 环境下仍可靠覆盖 `oneOf/anyOf/allOf` 分支与数组 items 中的 mapping key 检测（至少覆盖 `outputs[0].container.*` 与 `outputs.*.container.path` 的 `$init_var` 节点形态）。
- 明确重复诊断去重策略：优先输出更“可行动”的 unknown-fields（含 suggestions）诊断，避免 additionalProperties 造成的噪音。
- 建立测试基准，覆盖：缺失/异常 `jsonschema`、`oneOf/anyOf` + items 下 unknown-fields、重复诊断去重、以及 `$init_var` 节点形态错误的 fail-fast 路径与定位。

**Non-Goals:**

- 不新增/扩展 DSL 指令语法（例如不引入字符串插值型 `$init_var.xxx`）。
- 不重写 YAML schema 生成器；仅在必要时对校验器使用 schema 的方式做重构。
- 不改变 `yaml-dsl validate` / `yaml-dsl schema validate` 的 CLI 接口形态与参数集合（保持“开箱即用”）。

## Decisions

### Decision 1: 抽取统一的 schema issues collector

**选择**: 引入一个内部模块/函数（例如 `collect_jsonschema_issues(...)`），统一使用 `Draft7Validator.iter_errors(...)` 收集 schema 错误，并提供:

- 稳定排序（按 `absolute_path` + message）；
- 可选过滤策略（例如过滤 additionalProperties，以避免与 unknown-fields 重复）；
- 兼容两种调用方:
  - `yaml-dsl validate`：best-effort（缺依赖/非预期异常 → warning）
  - `yaml-dsl schema validate`：schema-only（缺依赖 → error）

**备选方案**:

- 继续在 `ConfigValidator` 与 CLI `schema validate` 中各自维护一套实现（拒绝：继续漂移）。
- `ConfigValidator` 仍用 `jsonschema.validate` 只报第一条，CLI 报多条（拒绝：诊断不一致、回归难定位）。

### Decision 2: unknown-fields 覆盖 `oneOf/anyOf` + items（best-match + 回退 union）

**选择**: 扩展 `find_unknown_fields(...)` 的 schema traversal，使其在无 `jsonschema` 环境下也能对 `oneOf/anyOf/allOf` 做尽可能准确的 unknown-fields 检测，并覆盖数组 items。

策略为“best-match 分支选择 + 回退 union”:

- **先过滤分支**: 依据当前 YAML value 的形态(dict/list/str/number/bool/null)过滤 `oneOf/anyOf` 候选分支（例如 dict 只匹配 `type: object` 的分支）。
- **再选择最匹配分支**: 对候选分支按“已知 key 命中数”打分，选择得分最高的分支作为 unknown-fields 的主依据（减少漏报）。
- **无法确定时回退 union**: 若分支无法区分（并列最高分/缺少 type 信息），则对分支的 `properties` 做 union，用“任一分支合法即视为已知 key”的规则兜底。
- **数组 items traversal**: 当路径段为数字索引（例如 `outputs.0`）且 schema 有 `items` 时，unknown-fields 递归时 MUST 进入 `items` schema 推导子节点的已知 key 集合。

说明:

- 分支间的“互斥/类型约束”仍由 schema 校验负责（如果 `jsonschema` 可用）。
- 该策略的目标是在不依赖 `jsonschema` 的情况下，让 strict unknown fields 的误报/漏报都尽量可控，且覆盖 `outputs[*]` 这类数组结构。

**备选方案**:

- 仅依赖 `jsonschema` additionalProperties（拒绝：可选依赖，且会产生重复诊断）。
- 为少数关键路径手写语义校验（可作为补充，但不应成为 unknown-fields 的主策略）。

### Decision 3: 重复诊断去重（unknown-fields 优先）

**选择**:

- schema collector 默认过滤 `additionalProperties` 类型的 schema errors；
- unknown-fields 负责输出“Unknown field …”并携带 suggestions；
- 对于不能由 unknown-fields 覆盖的 schema 错误（类型、enum、oneOf mismatch 等），schema collector 正常输出。

这样可以让用户看到更直接的“未知字段 + 建议”，同时仍保留 schema 结构/类型约束的诊断价值。

### Decision 4: `$init_var` 节点形态错误不依赖 jsonschema

**选择**:

- 在内部语义校验路径（`ConfigValidator.validate_report`）增加对 `outputs.*.container.path` 的结构校验（至少确保:
  - string 或单键 mapping `{$init_var: <non-empty-str>}`
  - mapping 不允许额外键）
- 解析与运行时保持同一套规则（通过共享 helper 函数/模块，避免 parser/runtime/validator 三处重复实现）。

备注: 本设计不强制把 `$init_var` 变量名 pattern 收紧到与 loader params 模板一致；是否要收紧作为后续可选增强（见 Open Questions）。

## Risks / Trade-offs

- [风险] schema errors 列表数量/排序变化 → [缓解] 明确稳定排序规则；在 tests 中固定关键场景的输出顺序。
- [风险] unknown-fields 在 `oneOf/anyOf` 下仍可能出现少量漏报/误报（分支选择不准或 schema 缺少 type 信息） → [缓解] 使用“best-match + 回退 union”降低漏报；并对关键路径（`outputs`、`container.path`）增加回归用例。
- [风险] 过滤 additionalProperties 可能隐藏某些 schema 错误细节 → [缓解] unknown-fields 提供更可行动信息；并保留非 additionalProperties 的 schema errors。

## Migration Plan

- 无需用户迁移配置。
- CLI 输出可能出现“错误条目去重、排序更稳定、schema 报错更完整”的变化；下游若做日志解析，应改为基于结构化 `--json` 输出（若使用）或按 path 前缀匹配，而非依赖错误行号/顺序。

## Open Questions

- 本次不收紧 `{$init_var: <name>}` 的 `<name>` 命名规则；若未来要统一 pattern（例如 `[a-zA-Z_][a-zA-Z0-9_]*`）需作为单独 change 评估破坏性影响并同步 schema。
- schema collector 的 `error.context`（oneOf 失败子错误）仅在 CLI `--verbose` 模式输出；默认输出保持简洁（避免噪音）。
