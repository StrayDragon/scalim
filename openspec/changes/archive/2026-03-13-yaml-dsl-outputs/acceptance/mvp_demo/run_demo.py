#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

from datetime import datetime
from pathlib import Path
import sys

from scalim.dsl.by_yaml import run


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    # Ensure `mvp_demo.*` is importable for YAML relative loader refs like `.loaders:...`.
    sys.path.insert(0, str(base_dir.parent))

    yaml_path = str(base_dir / "demo_detail.demand.yaml")
    output_path = "/tmp/scalim_mvp_demo.xlsx"
    _ = run(
        yaml_path,
        allowed_modules=frozenset([base_dir.name]),
        runtime_vars={
            "start_datetime": datetime.strptime("2026-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"),
            "end_datetime": datetime.strptime("2026-01-07 00:00:00", "%Y-%m-%d %H:%M:%S"),
        },
    )
    print("written:", output_path)


if __name__ == "__main__":
    main()
