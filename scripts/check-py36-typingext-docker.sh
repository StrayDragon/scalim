#!/usr/bin/env bash
set -euo pipefail

is_ci_enabled() {
    local v="${CI:-}"
    if [ -z "$v" ]; then
        return 1
    fi
    v=$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')
    case "$v" in
        0 | false | no)
            return 1
            ;;
    esac
    return 0
}

install_with_retry() {
    if is_ci_enabled; then
        python -m pip install -i https://pypi.org/simple "$@"
        return 0
    fi

    python -m pip install -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com "$@" || python -m pip install "$@"
}

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

tmp_root=$(mktemp -d /tmp/scalim-py36-typingext.XXXXXX)
trap 'rm -rf "$tmp_root"' EXIT
pycache_prefix="$tmp_root/pycache"
mkdir -p "$pycache_prefix"

python -m venv "$tmp_root/venv"
. "$tmp_root/venv/bin/activate"

py_is_legacy=$(
    python - <<'PY'
import sys
print("1" if sys.version_info[:2] < (3, 7) else "0")
PY
)

if [ "$py_is_legacy" = "1" ]; then
    install_with_retry --upgrade "pip<22" "setuptools<60" "wheel<0.38"
    install_with_retry "typing-extensions==4.1.1" "pyyaml>=5.4.1,<6.0.2"
else
    install_with_retry --upgrade pip setuptools wheel
    install_with_retry "typing-extensions==4.1.1" "pyyaml>=5.4.1,<6.0.2"
fi

PYTHONPYCACHEPREFIX="$pycache_prefix" PYTHONPATH="$repo_root/src" python -m compileall -q "$repo_root/src/scalim"
PYTHONPYCACHEPREFIX="$pycache_prefix" PYTHONPATH="$repo_root/src" python - <<'PY'
# 说明:
# - 该检查刻意不安装 openpyxl/pandas 等可选依赖,用于捕获“import 时炸”的回归.
# - compileall 仅能发现语法问题; import smoke test 才能覆盖注解求值差异等问题(Python 3.6 典型坑).

import traceback
from pathlib import Path

import scalim


def iter_scalim_modules():
    pkg_root = Path(scalim.__file__).resolve().parent
    src_root = pkg_root.parent
    modules = set()
    for path in pkg_root.rglob("*.py"):
        rel = path.relative_to(src_root).with_suffix("")
        parts = rel.parts
        if not parts or parts[0] != "scalim":
            continue
        if parts[-1] == "__init__":
            modules.add(".".join(parts[:-1]))
        else:
            modules.add(".".join(parts))
    return sorted(modules)


def star_import(module_name: str) -> None:
    # `import *` 会触发 `__all__`/注解求值等路径,更贴近“真实 import 边界”.
    ns = {}
    exec("from {} import *".format(module_name), ns)


failures = []
modules = iter_scalim_modules()

SKIP_STAR_IMPORT_MODULES = frozenset(
    [
        # 说明:
        # - 这些模块依赖可选 C-extension; 在 docker/不同架构下可能不可用(但主线功能可回退 pure-python)。
        # - 该门禁的目标是捕获 “关键入口/工作流模块 import 时炸” 的回归,不要求强行覆盖这些可选模块。
        "scalim.vendor.yamlx._yaml",
        "scalim.vendor.yamlx.ruamel.yaml.cyaml",
        "scalim.vendor.yamlx.yaml.cyaml",
    ]
)

tested_modules = [m for m in modules if m not in SKIP_STAR_IMPORT_MODULES]

for module_name in tested_modules:
    try:
        star_import(module_name)
    except BaseException as exc:
        failures.append((module_name, exc))
        print("")
        print("[fail] from {} import *".format(module_name))
        traceback.print_exc()

if failures:
    print("")
    print("[error] py36 import smoke failures: {}".format(len(failures)))
    for module_name, exc in failures:
        print("  - {}: {}: {}".format(module_name, type(exc).__name__, exc))
    raise SystemExit(1)

print("检查通过: py36 + typing-extensions 4.1.1 + import* smoke (modules={})".format(len(tested_modules)))
PY

SCALIM_PY36_TMP_ROOT="$tmp_root" PYTHONPYCACHEPREFIX="$pycache_prefix" PYTHONPATH="$repo_root/src:$repo_root/packages/scalim-misc/src" python - <<'PY'
# 说明:
# - 该检查用于覆盖更“真实”的运行路径: YAML 解析 + resolver + 执行 + CSV 输出.
# - 选择 `ecommerce_rank_score_report.yaml` 是因为它不依赖 openpyxl/pandas 等可选依赖,且输出可用纯 Python 计算做确定性对拍.

import csv
import os
from decimal import Decimal
from pathlib import Path

from scalim.dsl.by_yaml import run
from scalim_misc.demo_big_data_report.loaders import load_orders

repo_root = Path(".").resolve()
yaml_path = (
    repo_root
    / "notebooks"
    / "marimo"
    / "demo_big_data_report"
    / "chapters_of_yaml_dsl"
    / "declared_yaml_dsl"
    / "ecommerce_rank_score_report.yaml"
)
tmp_root = Path(str(os.environ["SCALIM_PY36_TMP_ROOT"]))
out_path = tmp_root / "ecommerce_rank_score_report.output.csv"

_ = run(
    str(yaml_path),
    allowed_modules=frozenset(["scalim_misc.demo_big_data_report.loaders"]),
    init_vars={"out_path_rank": str(out_path)},
)

with out_path.open("r", encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    actual_rows = list(reader)

# expected: pure python rebuild of `ecommerce_rank_score_report.yaml` semantics
groups = {}
for row in load_orders():
    region_id = int(row.get("region_id") or 0)
    category_id = int(row.get("product_category_id") or 0)
    quantity = int(row.get("quantity") or 0)
    unit_price = float(row.get("unit_price") or 0.0)
    discount_rate = float(row.get("discount_rate") or 0.0)

    final_amount = float(quantity) * float(unit_price) * float(discount_rate)
    key = (region_id, category_id)
    acc = groups.setdefault(
        key,
        {"region_id": region_id, "product_category_id": category_id, "order_cnt": 0, "sum_final_amount": Decimal(0)},
    )
    acc["order_cnt"] = int(acc["order_cnt"]) + 1
    acc["sum_final_amount"] = Decimal(str(acc["sum_final_amount"])) + Decimal(str(final_amount))

by_region = {}
for acc in groups.values():
    by_region.setdefault(int(acc["region_id"]), []).append(acc)

expected_rows = []
for region_id in sorted(by_region.keys()):
    bucket = by_region[region_id]
    bucket.sort(key=lambda r: (Decimal(str(r["sum_final_amount"])), int(r["product_category_id"])), reverse=True)

    prev_sig = None
    last_rank = 0
    for idx, r in enumerate(bucket):
        row_no = idx + 1
        sum_amount = Decimal(str(r["sum_final_amount"]))
        sig = "num:" + format(sum_amount, "f")
        if idx == 0:
            last_rank = 1
        elif prev_sig is None or sig != prev_sig:
            last_rank += 1
        prev_sig = sig
        r["rank"] = int(last_rank)
        r["row_no"] = int(row_no)

    for r in bucket:
        if int(r.get("row_no") or 0) > 2:
            continue
        rank_val = int(r["rank"])
        score = Decimal(100) - (Decimal(rank_val - 1) * Decimal(3))
        expected_rows.append(
            {
                "region_id": str(int(r["region_id"])),
                "product_category_id": str(int(r["product_category_id"])),
                "order_cnt": str(int(r["order_cnt"])),
                "sum_final_amount": str(Decimal(str(r["sum_final_amount"]))),
                "rank": str(int(rank_val)),
                "row_no": str(int(r["row_no"])),
                "score": str(score),
            }
        )

fields = ["region_id", "product_category_id", "order_cnt", "sum_final_amount", "rank", "row_no", "score"]


def stable_sort(rows):
    return sorted(rows, key=lambda r: (int(r["region_id"]), int(r["row_no"]), int(r["product_category_id"])))


actual_sorted = stable_sort(actual_rows)
expected_sorted = stable_sort(expected_rows)

if len(actual_sorted) != len(expected_sorted):
    raise SystemExit("py36 YAML demo failed: row count mismatch (actual={} expected={})".format(len(actual_sorted), len(expected_sorted)))

for idx, (a, e) in enumerate(zip(actual_sorted, expected_sorted)):
    for f in fields:
        if str(a.get(f)) != str(e.get(f)):
            raise SystemExit(
                "py36 YAML demo failed: mismatch at row {} field {}: actual={!r} expected={!r}".format(idx, f, a.get(f), e.get(f))
            )

print("检查通过: py36 YAML DSL run + CSV 输出对拍 (rows={})".format(len(actual_sorted)))
PY
