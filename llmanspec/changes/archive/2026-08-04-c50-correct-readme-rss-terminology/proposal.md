---
depends_on: []
branch: sdd/c50-correct-readme-rss-terminology
base_sha: a71d359bf4cdf2aad8b6aba0cd6a4ad276109c80
checkpointed: true
checkpoint_sha: a0a656f640029811692ad6cf049c9e4ecc019365
---

# Correct README RSS terminology and restore reader-first onboarding

## Why

根 README 已具备可执行的 Marimo 示例、注入漂移检查与图表资产，但首次阅读的路径仍有两个问题：

- 内存图与 README 将一次运行前后 RSS 的粗粒度差值称为「relative peak RSS」。实际实现没有在运行过程中采样峰值，因此该术语会把机制示意误包装成峰值测量。
- 安装、仓库开发命令、Pages 部署与示例治理细节出现在读者看到可理解用法之前；最小 Python/YAML 示例只给源码链接，失去 v0.10.1 README「先看两种 authoring 形状」的可读性优势。

这次变更要在不复制示例真相、不夸大性能承诺的前提下，使 README 成为面向报表/宽表用户的清晰着陆页。

## What Changes

- 修改 `governance-readme-examples`：
  - 将本地内存图的术语从「相对峰值 RSS」校正为「本地 RSS 增量代理」，明确它既不是采样峰值，也不是跨机器绝对 MB / SLA。
  - 规定 README 的可见 YAML quickstart fence 必须由 `example_readme_suite` 的可执行 SSOT 投影生成，并保留完整可运行源码入口。
  - 规定版本锚定的历史 A/B 性能叙事必须给出版本、工作负载边界、复现资料与非保证声明。
- 从现有的最小 YAML SSOT 生成一个读者可见、明确 loader 集成点的 YAML fence；Python IR 保持为高级入口链接，避免将当前内部 `ScalimEngine` 路径宣传为首选公开 API。
- 将 README 改写为「价值主张 → 安装 → YAML quickstart → 内存执行机制 → 有边界的历史 A/B 证据 → 进阶路径 → 质量与贡献」的读者优先结构，并移除首屏 Pages 部署细节与重复 FAQ。
- 使用 `write-precompute-0.10.json` 作为唯一数据源生成静态历史 A/B 图；将本地 RSS 图降为受限的机制示意，更新 SVG、alt text、章节与 notebook 文案以使用准确术语。
- 仅修正阻断本变更 `just qa` 的两处既有 py-doc-language 标注，使门禁可重新反映 c50 的质量状态；不改变其治理或生成行为。

## Capabilities

### Modified Capabilities

- `governance-readme-examples`: README 示例投影、RSS 图表语义与版本锚定性能主张的公开页治理。

## Impact

- 手工 README 文案：`README.md`（AUTOGEN 区块外）。
- 可执行示例 / 注入 SSOT：`notebooks/marimo/example_readme_suite/support/` 与对应 Marimo 章节。
- 生成资产：`docs/assets/readme/*.svg`；这些文件仍只能通过 README 生成入口刷新。
- 版本锚定数据源：`docs/doc/assets/data/write-precompute-0.10.json`（只读输入）；完整解释与复现入口保持在 `docs/doc/releases/write-precompute-0.10.md`。
- QA 基线标注：`scripts/check-doc-governance.py` 与 `scripts/gen-readme-examples.py`（仅语言检查兼容修正）。
- 验证：README 注入 drift、README suite headless gate、严格 SDD 校验与 `just qa`。

## Ethics

- `ethics.risk_level`: medium（公开性能/内存说法会影响用户预期）
- `ethics.prohibited_actions`: 将本地 RSS 差值称为真实峰值；把单次合成 A/B 夸大成通用性能或 SLA；在 README 外复制可运行示例真相；手工修改生成 SVG / AUTOGEN 内容
- `ethics.required_evidence`: 测量实现、版本化 benchmark JSON、可执行 README suite、注入器与严格 spec 校验
- `ethics.refusal_contract`: 缺少版本、环境和 workload 边界时，不发布数值性能主张
- `ethics.escalation_policy`: 若需要更换 benchmark 工作负载、把示意图改成真实峰值采样，或公开新的绝对内存数字，必须另行确认范围与测量方法