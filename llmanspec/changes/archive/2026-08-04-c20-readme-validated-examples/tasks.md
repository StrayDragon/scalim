# Tasks: readme-validated-examples

> Seams（已确认）：运行 gate exit 0；AUTOGEN drift；图资产一致；最小 Python/YAML 可跑；README 环境说明。  
> CI **不**强制相对内存比阈值。无 `bdd:`。

## 0. Specs landing

- [x] 0.1 新建 `llmanspec/specs/governance-readme-examples/spec.toon`（SSOT/注入/运行/drift/环境说明/资产）
- [x] 0.2 `governance-docs`：交叉引用 README 注入与生成入口
- [x] 0.3 `examples-marimo`：边界 requirement——README validated suite ≠ marimo 主线
- [x] 0.4 `llman sdd validate c20-readme-validated-examples --strict --no-interactive`

## 1. SSOT 骨架 + 运行 gate

- [x] 1.1 落地 `examples/readme/`（或 design 等价路径）：旋钮、naive、scalim、`run_all` 入口
- [x] 1.2 最小可跑 Python 示例（假数据，可断言产出行数/字段）
- [x] 1.3 最小可跑 YAML + runner（假 loader，同源可回归）
- [x] 1.4 `just readme-examples`：固定 CI scale 跑通；接入 `just qa`/`check`
- [x] 1.5 governance/单测：入口失败时非零退出可测（可选 tmp fixture）

## 2. 注入 + 图 + drift

- [x] 2.1 图表生成（相对峰值 SVG）+ 提交路径（如 `docs/assets/readme/`）
- [x] 2.2 README markers + injector（接入 `gen-docs` 或专用 just，SSOT/入口写清）
- [x] 2.3 drift/`--check`：区块与 SVG 不一致则失败；提示生成命令
- [x] 2.4 受控区外禁止平行手写可复制示例（治理脚本；范围钉死）

## 3. README 公开化叙事

- [x] 3.1 重写 `README.md` 手工骨架（安装/特性/链 docs）；插入 AUTOGEN markers
- [x] 3.2 环境说明段（口径、旋钮、非绝对 MB、如何重跑）
- [x] 3.3 跑 gen，确认注入代码与图正确渲染

## 4. 验证

- [x] 4.1 `just readme-examples` 绿
- [x] 4.2 gen `--check` / doc governance 绿
- [x] 4.3 人为改注入区块或跳过 gen → qa/drift 红
- [x] 4.4 `llman sdd validate` +（可选）相关 governance 单测绿
