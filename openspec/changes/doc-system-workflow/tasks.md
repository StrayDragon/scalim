## 1. 治理基线(规范 + 约束入口)

- [ ] 1.1 将 `openspec/changes/doc-system-workflow/specs/doc-governance/spec.md` 同步为主规范: 新增 `openspec/specs/doc-governance/spec.md`
- [ ] 1.2 按 delta 更新 `openspec/specs/docs-site/spec.md`(纠正 mkdocs.yml 叙述,允许受控 `*.gen.md`/导出 notebooks,并保持排除 specs/reports)
- [ ] 1.3 更新 `openspec/config.yaml`: 增补 doc governance 上下文 + per-artifact rules(要求 proposal/design/tasks 写明 SSOT/生成入口/漂移门禁)
- [ ] 1.4 更新 `AGENTS.md`: 增补“生成物/注入区块”规则(`.gen.*` + `SCALIM-GEN`),以及推荐生成入口(例如 `just gen`/`just gen-docs`)
- [ ] 1.5 处理 `CLAUDE.md` 与 `AGENTS.md` 的单源策略: 选择“生成/注入/严格一致性检查”之一并落规则(先解决关键事实漂移,如 `pyproject.toml` 的 `requires-python`)

## 2. 生成入口收敛与漂移门禁

- [ ] 2.1 定义 docs 生成入口: 选择并落地 `just gen-docs`(或把 docs 生成纳入 `just gen`),明确覆盖范围(`docs/doc/**/*.gen.md` + 注入区块 + notebooks 导出策略)
- [ ] 2.2 实现 docs drift check: 对 `docs/doc/**/*.gen.md` 与受控注入区块提供 `--check`/diff 失败机制,并给出明确修复提示(运行生成入口)
- [ ] 2.3 将 docs drift check 纳入 `just qa`(或 `quick-check-only-py`)并在 CI 强制执行
- [ ] 2.4 为生成输出引入确定性约束(排序/末尾换行/格式化),避免无意义 diff

## 3. docs-site: 引入受控 generated reference(方案 B 的最小集)

- [ ] 3.1 约定 generated reference 放置目录(建议 `docs/doc/_generated/` 或 `docs/doc/generated/`),并将其纳入 `docs/zensical.toml` 的 nav(显式收录)
- [ ] 3.2 从 YAML DSL schema 自动生成 reference 页面(例如顶层字段/definitions/枚举/默认值索引),输出为 `*.gen.md`
- [ ] 3.3 从 CLI 实现自动生成 reference 页面(例如 `yaml-dsl validate/schema/path/show` 的命令与参数索引),输出为 `*.gen.md`
- [ ] 3.4 为 OpenSpec specs 生成“索引页”(仅索引/链接,不把 specs 当站点页面),并以 `*.gen.md` 方式输出到 docs-site
- [ ] 3.5 将 `docs/doc/yaml-dsl/syntax.md`、`docs/doc/yaml-dsl/user-guide.md` 等高漂移章节中的“纯 reference 段落”迁移到 generated reference 或注入区块,手工页面改为“叙事 + 一层直达链接”

## 4. 复用已有生成器能力(降低实现成本)

- [ ] 4.1 评估是否复用 `scripts/gen-agent-skill.py` 的产物(如 `syntax-catalog.gen.md` / `cli-lsp-reference.gen.md`)作为 docs-site reference 的输入,并明确“SSOT → docs-site”路径(避免双份生成逻辑漂移)
- [ ] 4.2 把 `src/scalim/dsl/by_yaml/schema_dsl/doc_texts.py` 的模式推广为通用约定(例如 `doc_texts.py`/`DOC_TEXTS`),并补齐文档片段如何进入站点/生成物的流程说明
- [ ] 4.3 为注入区块替换逻辑提供统一 helper(避免多脚本各自实现正则替换导致边界不一致)

## 5. prompt 评测/调优(可选,后置)

- [ ] 5.1 引入 promptfoo(或等价工具)的 repo 级配置,并定义最小评测集: skill 触发/路由正确性 + 生成边界遵守(不改 `*.gen.*`/不改注入区块)
- [ ] 5.2 增加 `just prompt-eval`(或等价入口),并在 CI 中先作为非阻塞 job 运行(稳定后升级为门禁)

## 6. 验收

- [ ] 6.1 运行并通过: `just gen`(或 `just gen-docs`) + `just qa`
- [ ] 6.2 运行并通过: `just docs-build`(站点可构建) + `just docs-serve`(本地可预览)
- [ ] 6.3 运行并通过: `just openspec-check`

