# Design: README landing page, verified YAML projection, and honest RSS terminology

## Goals

- 让第一次打开 README 的报表/宽表用户先理解 Scalim 解决的问题，再看到一份 YAML 形状与可信性能边界。
- 保持 `notebooks/marimo/example_readme_suite/` 为 README 示例的唯一可执行 SSOT；README 只展示生成投影，不维护第二份完整示例。
- 将 RSS 图描述为运行前后本地 RSS 差值的相对代理，而不是运行中采样得到的峰值。
- 使用已发布、版本锚定的 `write-precompute` A/B 数据说明条件化性能收益，不制造通用加速承诺。

## Non-goals

- 不重新设计运行时内存采样器，不引入采样线程、memray 或新的峰值基准方法。
- 不将 notebook 开发环境、CLI 或 LSP 伪装成核心库的零配置安装体验。
- 不将 Python IR 内部 `ScalimEngine` 导入作为 README 首选公开 API。
- 不改变 YAML DSL、执行引擎或 benchmark 工作负载。

## Content architecture

README 手工区按下面的阅读顺序组织：

1. 精简徽章与一句人类可读的定位：宽表报告不必先整表常驻。
2. 仅给包使用者的安装命令；仓库 checkout / notebook / examples 命令移到贡献与探索说明。
3. YAML quickstart：受控 fence、`myapp.loaders` 集成点、完整且可运行的仓内 SSOT 链接。
4. 内存执行机制：字段按需、批处理、已消费数据释放；本地 RSS 增量代理仅作为折叠的机制示意。
5. 版本锚定性能证据：0.10.0 合成行式 sink A/B 图与简短限定，链接完整发布页、JSON 数据与复现说明；注明 0.10.1 发布说明延续该性能项。
6. YAML 与 Python IR 的分工、主线教程/工作流/事件扩展入口、质量与贡献入口。

GitHub Pages 部署配置、重复 FAQ、生成器内部操作细节不再占用首次阅读主线。

## SSOT and generation boundary

- `support/min_yaml_example.yaml` 继续是最小 YAML 的可执行配置真相。
- `support/min_yaml.py` 继续是运行该配置、allowlist 与结果断言的真相。
- `support/inject.py` 读取 YAML SSOT 并生成 README fence。为了让读者清楚自有应用的接入点，投影可将仓内 loader module 映射为 `myapp.loaders`，但必须：
  - 只替换声明的 loader module 前缀；
  - 明示它是接入点；
  - 紧邻完整、可运行 SSOT 与 fake loader 链接；
  - 由测试拒绝投影重新泄漏仓内 module 路径。
- Python IR 受控区继续生成来源链接和运行提示；README 手工文案将其定位为高级控制入口，并链接公开 `scalim.execution` 文档。
- `docs/doc/assets/data/write-precompute-0.10.json` 是历史速度图的唯一输入；渲染器不得手写速度数字。
- `chart_snapshot.json` 是本地 RSS 增量代理图的唯一输入；它不进入性能保证或硬门槛。
- `docs/assets/readme/*.svg` 都是生成资产，即使文件名没有 `.gen.`；只允许 `just gen-readme-examples` / `just gen-docs` 写入。

## RSS terminology correction

`measure_peak_delta_kb` 实际只读取函数执行前后两次 `/proc/self/statm`。实现会改名为准确的 RSS delta 名称，保留现有 `rss_kb_before`、`rss_kb_after`、`rss_kb_delta` 数据键。

所有 README suite 的用户可见文本、SVG 标题、alt text 和 spec 使用以下语义：

- 「本地 RSS 增量代理」或英文 `local RSS delta proxy`
- `naive = 1.0` 是同一 snapshot 内的相对基线
- 不是 sampled peak、不是绝对 MB、不是跨机器 SLA、CI 不对比例设阈值

为减少重复与误导性的百分比结论，README 只保留必要的代理图；任何删除的 SVG 都由生成器和 drift 检查同步处理。

## Versioned A/B evidence

README 的版本锚定性能段只陈述下列事实：

- Scalim 0.10.0；
- Python 3.6.15、`runs=1`、合成 workload、内存 sink、同一 plan 仅切换 `late_fields`；
- 行式 sink 的历史范围为约 1.47–1.60×；
- 输出值与 calculator 调用次数经全表对拍；
- 字段拓扑、sink、Python 和主机都会改变结果，因而不是性能保证。

静态 SVG 从 JSON 中选择行式 workload 并显示每个 shape 的比值；完整形状、列式数据和测量细节留在 release 文档，避免 README 重复维护数据表。

## Test seams

1. 注入 seam：生成器生成 YAML fence 与 benchmark/RSS 图；`--check` 能拒绝 AUTOGEN 或资产漂移，且测试验证 YAML 投影不包含仓内 loader 路径。
2. YAML execution seam：`example_readme_suite` headless runner 继续执行最小 YAML 真实 SSOT 并断言成功摘要。
3. chart semantics seam：测量 helper、章节文案、renderer、README alt text 与 SVG 不含 `peak` / 不准确的 RSS 节省承诺；生成资产与 SSOT 一致。
4. spec seam：更新后的 `governance-readme-examples` requirements/scenarios 通过严格 SDD 校验。
5. integration seam：执行相关生成入口、README examples check 和 `just qa`。

## Rollout and compatibility

这是文档和示例投影变更，不改变用户运行时 API 或 YAML 语法。现有 README 链接、`just examples` 及 `just gen-readme-examples` 保持入口兼容；只更新公开文案、生成输出与治理术语。
