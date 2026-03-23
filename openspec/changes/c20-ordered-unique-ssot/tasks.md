## 1. SSOT helper（ordered-unique-ssot）

- [ ] 1.1 在 `src/scalim/utils/` 下新增 SSOT helper（例如 `ordered_unique_str(items) -> Tuple[str, ...]`），并确保 Python 3.6 兼容
- [ ] 1.2 为 helper 增加最小 docstring 与导出（避免被误当作内部实现）

## 2. 替换重复实现并删除本地 `_ordered_unique`

- [ ] 2.1 `src/scalim/execution/derived_outputs.py` 改为使用 SSOT helper，并删除本地 `_ordered_unique`
- [ ] 2.2 `src/scalim/execution/output_composition.py` 改为使用 SSOT helper，并删除本地 `_ordered_unique`
- [ ] 2.3 `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` 改为使用 SSOT helper，并删除本地 `_ordered_unique`（若需要 list 返回，在调用点显式 `list(...)`）

## 3. Tests（可验证、可回归）

- [ ] 3.1 新增单测：`["a","a","b"]` 输出保序去重（tuple 形态）
- [ ] 3.2 新增单测：混合类型输入（例如 `["1", 1]`）的 `str()` 归一化与去重语义是显式且稳定的
- [ ] 3.3 （可选）增加 import/`rg` 校验，确保仓库内不再残留 `_ordered_unique` 重复实现（避免回归复制）

## 4. Final Gates

- [ ] 4.1 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
- [ ] 4.2 运行 `just qa`（或最小子集）确保无 lint/test 回归
