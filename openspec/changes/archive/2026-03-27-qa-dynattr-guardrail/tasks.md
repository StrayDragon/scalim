## 0. Baseline / Verification

- [x] 0.1 运行 `uv run scripts/check-dynattr.py --report .tmp/artifacts/dynattr.report.txt` 生成基线报告
- [x] 0.2 按目录/职责分类报告结果,识别“可静态化”与“必须 allow”的命中（见 `classification.md`）

## 1. Tooling

- [x] 1.1 实现 `scripts/check-dynattr.py`
- [x] 1.2 支持行级 `# pragma: allow-dynattr <prefix>: <detail>` 与文件级 `# pragma: allow-dynattr-file <prefix>: <detail>`
- [x] 1.3 支持文本报告、JSON 报告与 `--check` 非零退出码

## 2. Rollout

- [x] 2.1 优先重构低风险、已知字段的 `dynattr` 调用为静态访问
- [x] 2.2 对确属必要的动态边界补充 allow 注释与原因
- [x] 2.3 基线收敛后,将 `check-dynattr.py --check` 接入 `quick-check-only-py`
- [x] 2.4 接入后运行 `just qa` 并确认门禁通过
