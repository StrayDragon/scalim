## ADDED Requirements

### Requirement: Dev-only CPU profiling entrypoints exist (py-spy)
系统 MUST 提供 dev-only 的 CPU profiling 入口（例如 `py-spy` flamegraph），用于定位执行热路径的 CPU sampling hotspot。

该入口 MUST 满足：
- 默认 bench/CI 不依赖 `py-spy`（未安装时不影响 `pytest tests/bench -m bench` 的运行）
- profiling 产物 MUST 输出到稳定目录（例如 `.tmp/artifacts/perf/`），且不应被提交
- profiling 入口 MUST 使用仓库自带的自生成用例作为默认场景（例如 `demo_big_data_report`，默认 `BindingIr.mode=keys`，代表主路径）

#### Scenario: py-spy flamegraph is written to a stable directory
- **WHEN** 开发者运行 CPU profiling 入口（例如 `just profile-cpu`）
- **THEN** 系统生成 flamegraph 产物并写入 `.tmp/artifacts/perf/`（或等价受控目录）

#### Scenario: default benchmark suites do not require py-spy
- **WHEN** 环境未安装 `py-spy` 且开发者运行默认基准入口（例如 `just bench`）
- **THEN** 基准 MUST 正常运行（不得因为缺少 `py-spy` 而失败）
