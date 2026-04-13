## 1. Code fixes

- [x] 1.1 将 `workflow_compile.py` 中应保留链的 `from None` 改为 `from exc`（4 处）
- [x] 1.2 将 `workflow_config/_parse.py` 中对应包装改为 `from exc`（2 处）
- [x] 1.3 将 `project_config.py` 中对应包装改为 `from exc`（2 处）
- [x] 1.4 审查 `yaml_load.py`、`loader.py`、`conversion_sources.py`、`output_composition_yaml.py`、`_load.py` 等处的 `from None`，按规范改为 `from exc` 或为保留项补充抑制链原因注释

## 2. Governance (optional)

- [x] 2.1 暂不添加自动化 lint（per design: `from None` 是合法 Python 且有适用场景，通过 code review 规范执行）

## 3. Verification

- [x] 3.1 Run `just qa` / `just test-gate` to verify
- [x] 3.2 Run `just openspec-check` to validate artifacts
