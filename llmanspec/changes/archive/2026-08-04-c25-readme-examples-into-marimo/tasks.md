# Tasks: c25-readme-examples-into-marimo

## 0. Specs landing（Branch binding 后）

- [x] 0.1 改写 `llmanspec/specs/governance-readme-examples/spec.toon`：SSOT=`notebooks/marimo/example_readme_suite`；删「不得放入 marimo / 独立于 teaching line」类 req（含 r986）；保留注入 + 图表 drift + 相对比不硬闸
- [x] 0.2 改 `llmanspec/specs/examples-marimo/spec.toon`：删 r988；新增 README suite MUST 位于 notebooks、章节可导入、纳入 examples gate
- [x] 0.3 同步 `governance-docs` 交叉引用（r987 等）表述
- [x] 0.4 `llman sdd validate c25-readme-examples-into-marimo --strict`；commit Specs landing

## 1. Suite 骨架

- [x] 1.1 建 `notebooks/marimo/example_readme_suite/{demo_main.py,chapters/registry.py,support/…}`
- [x] 1.2 转写 `ch010_min_python` + 断言摘要 `[blocked-by: 1.1]`
- [x] 1.3 转写 `ch020_min_yaml`（含 loaders）`[blocked-by: 1.1]`
- [x] 1.4 转写 `ch030_memory_compare`（knobs/naive/scalim/measure）`[blocked-by: 1.1]`
- [x] 1.5 `demo_main` 调用 registry；本地 `SCALIM_EXAMPLES_SUITES=example_readme_suite just examples` 绿 `[blocked-by: 1.2, 1.3, 1.4]`

## 2. README / gen / 删旧

- [x] 2.1 迁移 inject/render_chart/snapshot 到 notebooks 侧或 `scripts/` 可引用路径；更新 `just gen-readme-examples`
- [x] 2.2 README AUTOGEN 指向新 SSOT；择优并入 stash 多图/FAQ（非伴侣双 SSOT）
- [x] 2.3 删除 `examples/readme/`；更新 governance tests / just `readme-examples`→并入 examples 或 drift-only
- [x] 2.4 更新 `AGENTS.md` 指针；去掉「独立于 marimo / 不进 examples」指引 `[blocked-by: 2.3]`

## 3. 门禁

- [x] 3.1 `just examples` 默认发现并跑 `example_readme_suite`
- [x] 3.2 `just gen-readme-examples --check`（或等价）+ `just qa` 相关子集绿
- [x] 3.3 勾选本 tasks；准备 verify
