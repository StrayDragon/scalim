## 1. Review Gate (Maintainer)

- [x] 1.1 维护者确认本 change 仅涉及诊断/定位,不改变 DSL 语义与接受的配置集合
- [x] 1.2 维护者确认 canonical path 口径选择: 点号分段 + 数字索引段(拒绝 bracket)

## 2. Path Normalization Utility

- [x] 2.1 新增 path normalization 工具函数: 将 `foo[0].bar[12]` 归一化为 `foo.0.bar.12`(建议落在 `src/scalim/dsl/by_yaml/config_parsing/yaml_load.py` 附近,供 CLI/loader/validator 复用)
- [x] 2.2 收敛现有重复的 path 清洗逻辑(例如 `↳` 前缀与 `(root)`): 用新的 normalization 统一替代 `yaml_load.py` / `validator.py` 中各自的 `_normalize_*_path` helper
- [x] 2.3 在 YAML location index 查找入口应用 normalization(例如 `error_loc_for_yaml_path` / `lookup_yaml_location`),确保 bracket path 也能找到精确位置
- [x] 2.4 在 issue→envelope 输出边界统一归一化 path(例如 `envelope_from_validation_issue`/CLI render),确保展示与 JSON 输出口径一致

## 3. Diagnostics Shape Dedup

- [x] 3.1 收敛至少一个已知重复校验点: `validate_unique_field_names` 的重复实现需统一为同一份 message/冲突信息(validator 产出 `ValidationIssue`,runtime compile 保留 `ValueError` 但复用同一 message builder; 覆盖 overrides.outputs 场景)
- [x] 3.2 更新相关文案与路径,确保 validate/compile/CLI 呈现一致结构与 canonical dot path

## 4. Tests

- [x] 4.1 新增回归测试: bracket path 的 issue 也能得到精确 `path:line[:column]` 定位
- [x] 4.2 更新 CLI 输出回归测试: 断言输出使用 canonical dot path,并覆盖至少一个数组索引定位场景

## 5. Quality Gates

- [x] 5.1 运行 `just openspec-check` 确保 OpenSpec 工件一致性
- [x] 5.2 运行 `just qa` 通过 lint/tests + drift checks
