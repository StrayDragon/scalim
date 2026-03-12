<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- `src/scalim/cli/yaml_dsl.py`
-->
# YAML CLI 参考(生成)

此页从 CLI 实现自动生成,用于对齐命令用法与参数说明.

## Commands

### `yaml-dsl validate`
- Help: Validate YAML DSL via internal validator
- Usage: `scalim-cli yaml-dsl validate [-h] [--schema SCHEMA] [--strict] [--json] [--verbose] yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl validate [-h] [--schema SCHEMA] [--strict] [--json]
                                    [--verbose]
                                    yaml_file

positional arguments:
  yaml_file             YAML 文件路径

options:
  -h, --help            show this help message and exit
  --schema SCHEMA, -s SCHEMA
                        JSON Schema 文件路径
  --strict              严格模式: 将未知字段视为错误
  --json                输出 JSON 结果
  --verbose, -v         显示详细错误信息
```

### `yaml-dsl schema validate`
- Help: Validate YAML DSL via JSON Schema
- Usage: `scalim-cli yaml-dsl schema validate [-h] [--schema SCHEMA] [--strict] [--json] [--verbose] yaml_file`
- Full help:
```text
usage: scalim-cli yaml-dsl schema validate [-h] [--schema SCHEMA] [--strict]
                                           [--json] [--verbose]
                                           yaml_file

positional arguments:
  yaml_file             YAML 文件路径

options:
  -h, --help            show this help message and exit
  --schema SCHEMA, -s SCHEMA
                        JSON Schema 文件路径
  --strict              严格模式: 将未知字段视为错误
  --json                输出 JSON 结果
  --verbose, -v         显示详细错误信息
```

### `yaml-dsl schema show`
- Help: Print JSON Schema
- Usage: `scalim-cli yaml-dsl schema show [-h]`
- Full help:
```text
usage: scalim-cli yaml-dsl schema show [-h]

options:
  -h, --help  show this help message and exit
```

### `yaml-dsl schema path`
- Help: Print JSON Schema path
- Usage: `scalim-cli yaml-dsl schema path [-h]`
- Full help:
```text
usage: scalim-cli yaml-dsl schema path [-h]

options:
  -h, --help  show this help message and exit
```
