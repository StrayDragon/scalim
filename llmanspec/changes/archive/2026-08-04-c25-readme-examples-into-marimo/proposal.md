---
depends_on: []
branch: sdd/c25-readme-examples-into-marimo
base_sha: 685133250009087585b748283fae188b4e1b877b
checkpointed: true
checkpoint_sha: b95ab72f9ac050bcb31a17ee02276c44da700db9
---

# README 示例转写为可校验 Marimo suite

## Why

`examples/readme/` 作为独立 SSOT + `just readme-examples` 与仓库主示例模型（`notebooks/marimo/**` + `just examples`）分裂：读者要两套入口，合约还用 r986/r988 **禁止**把 README suite 放进 marimo。目标是把 README 假数据示例 **转写** 为同构、可校验的 marimo 章节，纳入 `just examples`，删除 `examples/readme/` 与过时边界约束，并更新 AGENTS 指针。

stash 中有 README 多图/FAQ/伴侣页 WIP；apply 时择优并入本 change，**不**保留「薄封装 + 双 SSOT」形态。

## What Changes

- 新增 `notebooks/marimo/example_readme_suite/`（`demo_main` + `chapters*/registry` + 可导入 `run_*`），逻辑从 `examples/readme/` **转写**（非单纯移动包装）。
- README 受控 `AUTOGEN` 继续注入；指针/摘录以 notebooks 侧 SSOT 为真相；图表资产与 drift 保留（相对比仍不硬闸）。
- `just examples` **覆盖**该 suite；消化/合并 `just readme-examples` 运行职责（drift/`gen` 可保留独立目标或并入 docs gen）。
- 删除 `examples/readme/` 及对它的门禁/测试依赖。
- Specs：改写/收窄 `governance-readme-examples`；`examples-marimo` **删除 r988** 并新增「README suite 为 marimo 套件且进 examples gate」；`governance-docs` 交叉引用同步；更新根 `AGENTS.md` 指针。
- **不**启用 `bdd:`（复用既有 examples harness）。

**不改**

- 核心运行时 / YAML schema。
- CI 硬闸相对内存比阈值。
- 主线 `demo_big_data_report` 教学地位（README suite 是独立着陆套件，不是替代主线）。

## Capabilities

### Modified Capabilities

- `governance-readme-examples`：SSOT 改为 notebooks 侧；去掉「独立于 marimo / 不得放入 notebooks」类约束；保留 README 注入 + 图表 drift 语义（可收窄）。
- `examples-marimo`：删除 r988；新增 README validated suite 必须位于 `notebooks/marimo`、提供章节 SSOT、纳入 headless examples gate。
- `governance-docs`：交叉引用与生成入口表述对齐新 SSOT 路径。

### Removed / retired surface

- 目录 `examples/readme/`（实现删；合约不再以其为 SSOT）。
- AGENTS 中「README suite 独立于 marimo / 不进 examples」类指引。

## Impact

- **兼容**：库 API 不变；贡献者改 README 示例改为改 marimo 章节再 gen。
- **QA**：`just examples` 变长（小 scale 章节）；原 `just readme-examples` 运行面并入；drift 仍秒级。
- **公开化**：交互与 CI 同源，单一示例模型。

## Test seams（已锁定）

| Seam | 边界 | 断言方式 |
|------|------|----------|
| A | `just examples` → `example_readme_suite` chapters/`run_*` | headless PASS/FAIL 摘要；纳入 `just qa` |
| B | README `AUTOGEN` + `docs/assets/readme/*.svg` | `just gen-readme-examples --check`（或等价）drift |
| C | 禁止平行手写受控完整示例 | 既有 governance 检查（token / marker） |

## Ethics

- `ethics.risk_level`: low
- `ethics.prohibited_actions`: 保留 `examples/readme` 与 notebooks 双 SSOT；在默认分支改 live specs；CI 用绝对 MB/相对比作硬闸
- `ethics.required_evidence`: `just examples` 含 README suite 绿；注入/图 drift 绿；`examples/readme` 已删
- `ethics.refusal_contract`: 未删边界合约前不得声称「已融合进 marimo」
- `ethics.escalation_policy`: 若转写导致 examples 门禁显著变慢，须确认 scale/并行策略

## Open Questions — **已决议**

1. 路径。**已决议：propose（非 quick）；change id `c25-readme-examples-into-marimo`。**
2. WIP。**已决议：先 stash，apply 时择优并入。**
3. 门禁。**已决议：新 suite 纳入 `just examples`；消化 `just readme-examples` 运行职责。**
4. BDD。**已决议：不启用 `bdd:`。**