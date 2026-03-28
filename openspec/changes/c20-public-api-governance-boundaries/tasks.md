## 1. Public API manifest（SSOT）

- [ ] 1.1 选择 manifest 落点与格式（JSON/YAML/TOML），并新增机器可读文件（按稳定排序输出，避免漂移）。
- [ ] 1.2 实现 public surface 校验脚本：按 manifest 校验各模块 `__all__` 精确一致（缺失/新增均 fail-fast，错误可定位到模块与符号）。
- [ ] 1.3 将校验接入 `just qa`（或等价 gate），并确保本地/CI 行为一致。

## 2. Marimo public API suite 与 manifest 对齐

- [ ] 2.1 增加一致性校验：suite 覆盖的模块与符号集合必须与 manifest 对齐（避免二者各自演化）。
- [ ] 2.2 明确 suite 中可引用的导入路径仅来自 curated entrypoints（违反时 fail-fast）。

## 3. 收敛 public facades（禁止穿透 internal）

- [ ] 3.1 盘点当前 public facades 的 re-export（重点：`src/scalim/*/__init__.py`），识别 `_internal`/`events._*`/`dsl.by_yaml.runtime.*` 等泄漏点。
- [ ] 3.2 对需要保留稳定入口的包引入 `api.py`（或等价 facade 模块），将 public imports 指向 facade；同时停止 public `__init__` 直接 re-export internal。
- [ ] 3.3 更新 docs/skills/examples 的导入示例，仅使用 manifest 的 curated entrypoints（涉及 docs 注入/生成时通过 `just gen-docs` 刷新并通过 drift gate）。

## 4. 用户材料导入治理 gate（docs/skills/examples）

- [ ] 4.1 增加静态扫描 gate：拒绝用户材料引用 internal 路径（窄且确定：`_internal`、`events._*`、`dsl.by_yaml.runtime.*`、以及其它未编目的路径）。
- [ ] 4.2 gate 失败信息给出替代导入路径与迁移建议（以 manifest 为准）。

## 5. 验收与回归

- [ ] 5.1 运行 `just examples`，确保 public API suite 仍通过且覆盖面与 manifest 一致。
- [ ] 5.2 运行 `just qa` 与 `just openspec-check`，确保门禁与规范校验通过。

