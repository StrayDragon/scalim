## 1. Code fixes

- [ ] 1.1 将 `workflow_compile.py` 中应保留链的 `from None` 改为 `from exc`（约 4 处，按 design 清单）
- [ ] 1.2 将 `workflow_config/_parse.py` 中对应包装改为 `from exc`（约 2 处）
- [ ] 1.3 将 `project_config.py` 中对应包装改为 `from exc`（约 2 处）
- [ ] 1.4 审查 `yaml_load.py`、`loader.py`、`conversion_sources.py`、`output_composition_yaml.py` 等处的 `from None`，按规范改为 `from exc` 或为保留项补充抑制链原因注释

## 2. Governance (optional)

- [ ] 2.1 若采用自动化手段：添加治理测试或 lint 规则，防止新增不符合规范的 `from None`（无注释或错误边界）

## 3. Verification

- [ ] 3.1 Run `just qa` / `just test-gate` to verify
- [ ] 3.2 Run `just openspec-check` to validate artifacts
