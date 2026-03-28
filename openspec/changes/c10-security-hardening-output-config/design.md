## Context

本仓库同时存在两类“输入”：

- **数据输入**：来自 loader 的行数据，常包含不可信字符串；最终会通过 sinks/workflow resources 输出到 CSV/Excel 等下游常用格式。
- **配置输入**：YAML DSL 支持 imports、模板预编译（`template_vars`）与 Python 引用解析（allowlist/trusted-mode），具备较强的“config-as-code”属性。

在这些输入参与到“文件输出”“错误消息”“可观测性落盘”时，如果缺少安全默认与明确 opt-in，将很容易把框架从“报表生成”变成“执行/泄露/DoS 的载体”。

约束：
- 运行时核心代码需保持 Python 3.6 兼容（不使用 3.10+ 语法特性）。
- `.gen.*` 与 `BEGIN/END AUTOGEN` 区块为生成物/注入区块（禁止手改；入口 `just gen-docs`）。
- 本阶段不扩展 `openspec/sanitize_rules.yaml`（隐私/发布治理规则不在此 change 内推进）。

## Goals / Non-Goals

**Goals:**
- CSV 输出具备与 Excel 输出一致的“疑似公式字符串”安全默认（escape by default），并提供显式 opt-out（可信场景允许写公式/原样写出）。
- `template_vars` 预编译具备明确的资源上限（渲染后长度/片段数量等），并在超限时 fail-fast，错误消息不泄露渲染结果文本。
- 将高风险入口（trusted/unsafe）与公共文档/skills 的使用路径隔离：默认公共入口不提供隐式逃逸口子；repo 层面可审计/可 gate。

**Non-Goals:**
- 不在此变更内做大范围 API 重构（例如全面拆分 public facades / `_internal` re-export 收敛）。
- 不在此变更内扩展 OpenSpec sanitize 覆盖面或规则（后续另开 P2 发布治理变更处理）。
- 不在此变更内解决所有并发写入与确定性顺序问题（这些属于 workflow 并发/确定性 change）。

## Decisions

### 1) CSV 公式注入防护：与 Excel 规则对齐，默认 escape

决策：
- 复用现有 Excel 公式转义规则（`= + - @`，允许忽略前导空白）作为 CSV 的默认安全策略。
- 在 CSV sinks 上增加显式开关（建议命名倾向 `allow_formulas: bool = False`，与 workflow workbook 资源的 `allow_formulas` 语义对齐），以便可信场景 opt-out。

理由：
- 公式注入是典型“数据->文件->人类工具”链路漏洞；框架应默认保护。
- 与现有 Excel 规则对齐可以减少心智负担与实现分叉（同一套转义工具函数/测试用例）。

备选方案：
- 仅在文档警告、不做默认保护：拒绝（风险外溢到所有用户，且常被忽略）。
- 在 CSV 层引入复杂的 CSV-specific 规则：暂不做（优先一致、窄且确定）。

### 2) 模板预编译增加渲染后上限（硬限制）

决策：
- 在 `template_vars` 启用时，对每次渲染产物（包括 imports fragments）做 **渲染后长度上限** 检查；超限 fail-fast。
- 上限值作为可配置参数/选项（默认值保守，且在 public API 与 workflow/CLI 入口一致）。
- 错误消息只暴露：发生位置（demand/workflow/fragment 路径）+ 实际长度 + 上限值，不回显渲染文本。

理由：
- 模板渲染属于“纯文本放大器”；在不可信配置场景下非常容易造成 DoS。
- 渲染后长度是“窄且确定”的可实现约束，不依赖复杂的执行计数或解释器插桩。

备选方案：
- 仅限制输入 YAML 原始长度：拒绝（模板可能放大输出）。
- 通过解释器级别限制循环次数：复杂且与 litejinja2 实现深度耦合，后续再评估。

### 3) 高风险入口治理：把“可用”与“可被引用”分开

决策：
- 保留 trusted/unsafe 能力作为“内部/测试能力”，但在 repo 层面增加显式 gate，禁止 docs/skills 引用这些入口（避免扩散为公开教程）。
- gate 采用简单可解释的静态扫描（例如 `rg` 搜索禁用导入路径），失败时给出迁移建议。

理由：
- 安全能力本身可能仍有价值（内部演示、回归测试），但其“传播路径”必须可控。

备选方案：
- 直接删除 unsafe/trusted 能力：本阶段不做（会造成现有 internal 用例迁移成本陡增）。

## Risks / Trade-offs

- [兼容性] CSV 输出默认 escape 可能改变下游打开体验（例如原本想写公式）：→ 提供显式 `allow_formulas=True` opt-out，并在文档明确默认策略。
- [误报/漏报] 公式前缀规则是启发式：→ 规则保持“窄且确定”（首字符集合 + lstrip），并与 Excel 规则一致；后续如需扩展再另开变更。
- [资源上限选择] 默认上限过小会误伤大 YAML：→ 上限可配置；并在错误信息提示如何调整（但不回显内容）。
- [治理误伤] docs/skills 静态扫描可能误报：→ 仅禁用明确的导入路径（例如 `unsafe_entrypoints`），允许在内部开发文档（非公开）通过显式 whitelist 目录承载（若确有需要）。

## Migration Plan

- 阶段 1：落地 CSV/模板上限的实现 + 单测；更新对应 specs 并确保 `just openspec-check` 通过。
- 阶段 2：补充 docs（仅在 SSOT 文档中说明默认安全行为与 opt-out），并加入 QA gate（例如 `just qa` 中的静态扫描）。
- 回滚策略：开关保留（`allow_formulas`/上限参数）；若默认策略造成严重兼容问题，可在一个版本窗口内临时调整默认值并给迁移告警。

## Open Questions

- CSV sinks 的开关命名最终选用 `allow_formulas` 还是 `escape_formulas`？（倾向 `allow_formulas` 与 workbook 资源一致。）
- 模板渲染上限默认值应设为多少更合适？是否需要分别限制 demand/workflow 与 fragments？

