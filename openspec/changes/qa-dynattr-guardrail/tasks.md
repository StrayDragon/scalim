## 0. Baseline / Verification

- [ ] 0.1 运行 `uv run scripts/check-dynattr.py --report .tmp/artifacts/dynattr.report.txt` 生成基线报告
- [ ] 0.2 按目录/职责分类报告结果,识别“可静态化”与“必须 allow”的命中

## 1. Tooling

- [ ] 1.1 实现 `scripts/check-dynattr.py`
- [ ] 1.2 支持行级 `# pragma: allow-dynattr <reason>` 与文件级 `# pragma: allow-dynattr-file <reason>`
- [ ] 1.3 支持文本报告、JSON 报告与 `--check` 非零退出码

## 2. Rollout

- [ ] 2.1 优先重构低风险、已知字段的 `dynattr` 调用为静态访问
- [ ] 2.2 对确属必要的动态边界补充 allow 注释与原因
- [ ] 2.3 基线收敛后,将 `check-dynattr.py --check` 接入 `quick-check-only-py`
- [ ] 2.4 接入后运行 `just qa` 并确认门禁通过
