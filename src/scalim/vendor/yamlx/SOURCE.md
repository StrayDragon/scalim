# yamlx provenance

本目录 vendors 化 `YAML` 解析实现,以支持下游老项目(`Python 3.6`、不可随意安装第三方依赖)仅同步 `src/scalim/` 源码即可运行(见 `scripts/vendor-sync.py` 与 `openspec/specs/legacy-vendors-sync/spec.md`)。

## Upstream

- PyPI distribution: `PyYAML==6.0.1`
  - Vendored as: `src/scalim/vendor/yamlx/yaml/`
  - License: MIT (see `LICENSE.PyYAML-6.0.1.txt`)
- PyPI distribution: `ruamel.yaml==0.18.3`
  - Vendored as: `src/scalim/vendor/yamlx/ruamel/yaml/`
  - License: MIT (see `LICENSE.ruamel.yaml-0.18.3.txt`)

## License acquisition (verbatim from PyPI sdist)

为保证许可证文本准确可追溯,本目录中的许可证文件由对应版本的 PyPI `sdist` 包内提取并原样保存:

- `LICENSE.PyYAML-6.0.1.txt` 来自 `PyYAML-6.0.1.tar.gz` 的 `LICENSE`
- `LICENSE.ruamel.yaml-0.18.3.txt` 来自 `ruamel.yaml-0.18.3.tar.gz` 的 `LICENSE`

原因:

- 下游通过 vendors 同步直接分发/运行这些第三方源码/二进制产物;将许可证文本随 vendors 一并同步,可降低合规风险并提升可审计性。

## Vendored files & local modifications

- `yaml/` (PyYAML)
  - 修复 vendors 场景下的导入正确性,避免误导入系统 `site-packages/yaml`。
  - 为 C-extension 初始化提供 `sys.modules["yaml"]` alias,保证下游未安装 `PyYAML` 时可加载 `_yaml`。
- `ruamel/yaml/` (ruamel.yaml)
  - 增加导入期 bootstrap,将 vendors 化包注册为 `ruamel`/`ruamel.yaml`,以稳定解析上游大量的绝对导入(`ruamel.yaml.*`)。
  - 在可加载时将 `scalim.vendor.yamlx._ruamel_yaml*.so` 映射为顶层 `_ruamel_yaml`,便于启用 clib;失败则自然回退 pure-python。
- Native extensions
  - `src/scalim/vendor/yamlx/yaml/_yaml.cpython-36m-*.so` (PyYAML libyaml extension, CPython 3.6)
  - `src/scalim/vendor/yamlx/_ruamel_yaml.cpython-36m-*.so` (ruamel YAML clib extension, CPython 3.6)

## Update procedure

1. 选择目标上游版本(必须覆盖下游 `Python 3.6` 运行时边界)。
2. 用上游版本替换 vendors 源码,并重新准备对应 `CPython 3.6` 的二进制扩展(如需).
3. 从上游 `sdist` 更新许可证文件(保持原样),并更新本文件与 `src/scalim/vendor/README.md` 的版本信息。
4. 运行 `just qa` 与 `just py36-compat-check`(或下游 vendors 模拟导入)确保导入链路与解析能力稳定。

