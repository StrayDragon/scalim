# 0.20.0 Breaking 追加（Stage B · c53-yaml-dependency-unvendor）

1. **运行时新增依赖 `ruamel.yaml>=0.19.1`**：YAML 后端从内置 vendor 切换为 PyPI 依赖（YAML 1.2 语义不变，spike 三后端对拍零差异）；安装 scalim 将自动携带。
2. **`scalim.vendor.yamlx` 命名空间移除**（vendored ruamel 0.18.3 + vendored PyYAML 6.0.1 + cp36 `.so`）：直接使用 `ruamel.yaml` / `yaml`(仅 dev 对拍) 即可。
3. **wheel 体积显著下降**（vendor 树约 5.8MB，含 3.1MB cp36 不可加载二进制，全部移出发布物）。
4. **`dump_effective_demand_yaml`（review/debug 用途）的排版可能随 ruamel 版本变化**：load 语义与 rt 字节幂等合约不变；依赖声明为下界 `>=0.19.1` 无上界。
