---
depends_on: []
branch: sdd/c20-readme-validated-examples
base_sha: 72905cc29a86a2a2176b9645b292be34c5a4b3ea
checkpointed: true
checkpoint_sha: 72905cc29a86a2a2176b9645b292be34c5a4b3ea
---

# 公开化 README：可校验示例 + 内存对比叙事

## Why

仓库准备从 private 公开化，但根 `README.md` 长期未更新：Python 示例含 `NotImplementedError`，YAML 仅为示意，**任何 fence 都未进入 `just qa`**。公开页若继续展示漂移/不可跑代码，会直接损害可信度。

目标是建立可复用治理：README 中可复制代码块 **MUST** 来自可跑 SSOT 并经注入 + drift 门禁；并突出典型价值——内存不友好写法 vs 等价 Scalim 实现（全假数据、全局旋钮、提交相对占比图 + 环境说明）。

## What Changes

- 新增 README 示例 SSOT（建议 `examples/readme/` 或等价）：旋钮常量、naive baseline、Scalim 路径、最小可跑 Python/YAML 示例、图表生成。
- 根 `README.md` **全面重写**公开化叙事；受控 fence / 图通过 `<!-- BEGIN/END AUTOGEN:... -->` 注入（禁止手写受控可复制块）。
- 生成入口接入 `just gen-docs`（或专用 `just` 目标并由 gen-docs/qa 调用）；drift 进 `just qa`。
- 运行 gate：`just readme-examples`（命名可微调）纳入 `just qa`——**跑通 + drift**；**不**强制相对内存比阈值（CI 机器噪声）；相对比与 SVG 由生成流程产出并提交，README 旁写清环境/口径。
- Specs：新建 `governance-readme-examples`；`governance-docs` 交叉引用；`examples-marimo` 声明 README suite 边界（≠ marimo 主线）。

**不改**

- 核心运行时行为 / YAML schema。
- 启用 `bdd:` runner。
- CI 硬闸绝对 MB 或相对内存比阈值（本 change 明确排除；本地/文档可展示相对比）。

## Capabilities

### New Capabilities

- `governance-readme-examples`：README 受控示例 SSOT、注入、运行与 drift 合约。

### Modified Capabilities

- `governance-docs`：指向 README 注入/生成入口与 drift 归属。
- `examples-marimo`：明确 README validated suite 不是 marimo 教学主线，不得互相替代。

## Impact

- **兼容**：库 API 不变；公开叙事与贡献者维护成本上升（改示例须改 SSOT 再 gen）。
- **QA**：`just qa` 增加 README 示例运行 + 注入漂移检查（应保持秒～十秒级小 scale）。
- **公开化**：README 成为可验证价值主张入口。

## Doc ownership

| 工件 | 角色 | 生成入口 |
|------|------|----------|
| `examples/readme/**`（路径 apply 时可微调） | SSOT | 手工 |
| `README.md` 受控 `AUTOGEN` 区块 | 注入 | `just gen-docs` / README 生成目标 |
| `docs/assets/readme/**`（或等价）提交的 SVG | 生成资产 | 同上；qa drift |
| `llmanspec/specs/governance-readme-examples/` | 合约 | Specs landing |

## Ethics

- `ethics.risk_level`: low
- `ethics.prohibited_actions`: 在 README 受控区手写不可追溯 fence；CI 用绝对 MB 作硬闸；把 README suite 塞进 marimo SSOT 造成双真相
- `ethics.required_evidence`: SSOT 脚本在 CI scale 下 exit 0；`--check`/drift 失败可复现；README 含环境说明
- `ethics.refusal_contract`: 无注入 markers + drift 方案不得声称「README 示例已校验」
- `ethics.escalation_policy`: 若生成图依赖过重（matplotlib 等）影响默认依赖面，须升级确认（优先无新 runtime dep：纯 SVG / 已有 dev 工具）

## Open Questions — **已决议**

1. SSOT 方式。**已决议：注入式（脚本 SSOT → AUTOGEN → drift）。**
2. README 范围。**已决议：全面重写叙事 + 修好最小 Python/YAML 可跑示例 + 内存 A/B。**
3. 图与数字。**已决议：提交 SVG/PNG（相对比例）；CI 只跑通 + drift；配环境说明；不强制相对比阈值。**
4. Spec 落点。**已决议：新建 `governance-readme-examples` + `governance-docs` 交叉引用 + `examples-marimo` 边界句。**
5. BDD。**已决议：不启用 `bdd:`。**