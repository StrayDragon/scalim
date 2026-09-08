# Design: Stage B YAML 去 vendor

## 关键设计决策（Stage B-0 spike 证据支撑）

| 决策点 | 结论 | 依据 |
|---|---|---|
| 依赖范围 | `ruamel.yaml>=0.19.1`，**无上界** | 0.19 为当前维护线（0.18.17 为遗留线）；spike 证明 0.19.1 与 vendored 0.18.3 load 语义零差异 + rt 字节幂等成立；clib 加速经 `ruamel.yaml.clibz` 自动携带 |
| 对拍基线 | 保留 `test_yaml_backend_migration.py`：上游 ruamel vs **dev 组 PyYAML** | PyYAML 仅作迁移期 oracle（YAML 1.1 差异已在 corpus 内规避）；降级为 dev 依赖后不再进入用户安装面 |
| import 策略 | 运行时 2 处改 `from ruamel.yaml import YAML`；工具包 import 路径不变 | vendored 的 sys.modules 别名使 `from ruamel.yaml.comments import ...` 天然兼容上游，工具包零改动 |
| dump 排版漂移 | 不视为破坏 | `dump_effective_demand_yaml` 仅 review/debug 用途；contract 只锚定 load 语义与 rt 幂等（spike 已证） |
| `yaml_base_dict_type`/`construct_mapping` patch | 保持原实现，仅换 import | spike 在 0.19.1 上按同一 patch 跑通全部用例 |
| vendored PyYAML | 删除（不保留为审计快照） | 对拍 oracle 改用 dev 安装的 PyYAML（版本透明、可升级）；历史快照在 git 历史中可追溯 |
| cp36 `.so` | 随 yamlx 树删除 | floor 3.10 起即不可加载（Stage A 已论证） |

## 文档/生成边界（Artifact 规则）

- **手工 SSOT**：`pyproject.toml`、`src/scalim/dsl/yaml_dsl/_internal/config_parsing/{yaml_load,effective_yaml}.py`、`scripts/{sanitize,check-staged-sanitize}.py`、`src/scalim/vendor/README.md`、ruff/basedpyright 配置段。
- **生成物**：预期无 `.gen.` 变化（YAML 语料不变）；若治理检查报 drift，按 `just gen-docs` 刷新。
- **injected blocks**：不触碰。

## Drift gate

- `llman sdd validate --all --strict --no-interactive`（工件改动后）。
- `just check-only-py`（lint/type/100% 覆盖 + corpus 对拍）；发布前 `just qa`。

## 风险与回滚

- 单分支线性提交；删除 yamlx 为独立 commit，可整体 revert。
- 风险 1：0.19 在 CI/用户平台需有 wheel（`ruamel.yaml` 纯 Python 回退 + `clibz` 二进制 wheel 均已发布 3.9+ 平台；CI matrix 实测兜底）。
- 风险 2：`yaml_base_dict_type` 等半公开 API 在 0.19 的行为差异——spike 的 constructor-patch 用例已覆盖；若后续 0.19.x 小版本破坏，以下界 `>=0.19.1` + 对拍测试在 CI 拦截。
- 风险 3：`scripts/sanitize.py`/`check-staged-sanitize.py` 切 PyYAML 后输出格式差异——两者仅做安全清洗（字符串替换/重序列化），断言以清洗后语义为准。
