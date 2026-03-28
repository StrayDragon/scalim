## Why

YAML DSL 是 Scalim 的核心 SSOT 入口之一，但当前在“加载/定位/校验/错误结构/常量来源”上存在多套实现与分叉（CLI、compile/run、workflow validate、imports fragments）。这会带来三类问题：

- 行为不一致：同一份 YAML 在不同入口下报错结构与容错策略不一致，用户难以理解与定位。
- 维护成本高：枚举/默认值/描述文本分散在 schema_dsl、validator、parser 乃至局部常量中，容易出现口径漂移。
- 演进受阻：每次引入新字段/语义都需要在多处同步修改，且缺少统一的回归与 SSOT 约束。

## What Changes

- 引入统一的 YAML 加载与定位 facade（一个入口负责：duplicate key 检测、location index、imports fragment 复用、统一错误结构）。
- 将 DSL 的枚举/默认值/描述文本收敛到 schema_dsl 为主的 SSOT，并为 validator/parser 增加一致性自检（避免“改 schema 忘了改 runtime”）。
- 统一 CLI validate / schema validate / workflow validate 的错误输出结构与可诊断性（同一错误在不同入口可复现）。
- 明确 schema 分发链路：Python 侧生成 schema 与 editor 侧 schema 复制/分发必须可审计、可验证、可 drift gate。

## Capabilities

### New Capabilities

- `yaml-dsl-unified-loader`: 统一 YAML load/locate/error facade（作为 DSL 基础设施 SSOT）。

### Modified Capabilities

- `yaml-dsl-cli-validation`: CLI 校验的错误结构与定位口径与 runtime/compile 保持一致。
- `yaml-dsl-schema`: 枚举/默认值/markdownDescription 的 SSOT 收敛与一致性自检。
- `yaml-dsl-workflow-validate`: workflow validate 与 demand compile 的 parse/validate 行为一致（至少在 duplicate key / imports / location / error envelope 上一致）。
- `yaml-dsl-editor-schema-blocks` / `yaml-dsl-editor-core`: editor schema 分发链路与 Python 侧 schema 生成保持一致并可 drift gate。

## Impact

- 受影响代码（SSOT）：`src/scalim/dsl/by_yaml/**`（loader、location index、parsers/validators、CLI validate、workflow validate）；以及 schema 生成脚本与 editor schema 分发脚本。
- 受影响测试：需要补充一致性回归（同 YAML 在 CLI/compile/workflow validate 下报错结构一致）。
- 受影响文档：`docs/doc/yaml-dsl/**`（SSOT 文档；若涉及生成/注入区块则通过 `just gen-docs` 刷新）。

