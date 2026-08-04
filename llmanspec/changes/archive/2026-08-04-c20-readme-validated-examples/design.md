# Design: README validated examples

## 目标架构

```text
examples/readme/                    # SSOT（路径可微调，须单一目录）
  knobs.py / constants              # N_ROWS, N_FIELDS, BATCH_SIZE, … 用户可改
  naive_baseline.py                 # 内存不友好：全量物化 / 全列常驻
  scalim_path.py                    # 等价 Scalim：批处理 + 剪枝/流式 sink
  min_python_example.py             # 最小可跑 Python 闭环（假数据）
  min_yaml_example.yaml + runner    # 最小可跑 YAML（假 loader）
  render_chart.py                   # 相对峰值比 → 提交用 SVG
  run_all.py                        # gate 入口：跑通断言（不做比阈值硬闸）

        │ just readme-examples（qa）
        │ just gen-docs / gen-readme-examples
        ▼
README.md  <!-- BEGIN AUTOGEN:readme-*-example --> … <!-- END … -->
docs/assets/readme/*.svg            # 提交资产；旁注环境说明（手工段）
```

## 决策

| 主题 | 选择 | 理由 |
|------|------|------|
| SSOT | 脚本 + 注入，非 doctest README | 对齐 `governance-docs` / CLI snippet 治理；多文件与图友好 |
| CI 内存比 | **不**硬闸相对阈值 | 用户决议；机器噪声；本地/图仍展示相对比 |
| 图格式 | 提交 SVG | 可 diff、无位图噪声；尽量零新 runtime 依赖（手写 SVG 或 stdlib） |
| 与 marimo | 独立 suite | marimo 是教学主线；README 是公开着陆页 gate |
| 测量口径 | 相对峰值（naive=1.0）+ 环境说明 | 绝对 MB 不作承诺 |

## Gate 分层

1. **Run**：小 scale 固定旋钮，naive + scalim + min examples 均 exit 0；可选写出 JSON 到 `.tmp/`（不提交）。
2. **Inject/Drift**：AUTOGEN 区块与生成器输出一致；缺失 marker / 手写受控前缀失败（风格对齐 `yaml_dsl_cli_snippet_governance`）。
3. **Assets**：提交的 SVG 与 generator 在 CI scale 下字节或规范化文本一致（或 gen 后 `--check`）。

## README 叙事骨架（apply 时落文）

1. 一句话价值 + 安装
2. 内存对比（注入代码 + 图 + **环境说明**）
3. 最小 Python / YAML（注入）
4. 特性摘要（可缩，链到 docs）
5. 质量保证 / 贡献入口

环境说明至少包含：测量 OS/Python 大类、旋钮默认值、相对比含义、非跨机绝对 MB 承诺、如何改旋钮重跑。

## 非目标

- 把 demo_big_data_report 整套搬进 README
- pytest-bdd / `bdd:` 
- 用真实业务数据
- 替换现有 `examples` marimo gate

## 风险与缓解

- **依赖膨胀**：图生成优先纯 SVG 字符串；避免把 matplotlib 拉进默认 runtime。
- **双真相**：禁止 README 手写与 SSOT 平行的「完整示例」；治理脚本拒绝受控区外的复制型 fence（范围在 apply 钉死：至少 python/yaml 受控块）。
- **qa 时长**：CI scale 行数足够展示相对趋势即可（例如数百～数千行级），不得拖垮 `just qa`。
