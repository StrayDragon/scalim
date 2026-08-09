#!/usr/bin/env python3
"""Export demand/workflow JSON Schema property paths for c40 inventory.

Writes under `.tmp/c40-yaml-field-inventory/` (rebuildable; do not commit).
"""

from __future__ import print_function

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _repo_root():
    # llmanspec/changes/c40-.../thisfile -> parents[3] == repo root
    return Path(__file__).resolve().parents[3]


def walk_props(schema, node, path, out, defs=None, seen=None):
    if seen is None:
        seen = set()
    if defs is None:
        defs = schema.get("$defs") or schema.get("definitions") or {}
    if not isinstance(node, dict):
        return
    if "$ref" in node:
        name = node["$ref"].split("/")[-1]
        key = (path, name)
        if key in seen:
            return
        seen.add(key)
        target = defs.get(name)
        if target:
            walk_props(schema, target, path, out, defs, seen)
        return
    for k in ("oneOf", "anyOf", "allOf"):
        for alt in node.get(k) or []:
            walk_props(schema, alt, path, out, defs, seen)
    props = node.get("properties") or {}
    for k, v in props.items():
        p = "{}.{}".format(path, k) if path else k
        if not isinstance(v, dict):
            out.append({"path": p, "type": type(v).__name__})
            continue
        row = {"path": p}
        if "type" in v:
            row["type"] = v["type"]
        if "enum" in v:
            row["enum"] = v["enum"]
        if "$ref" in v:
            row["ref"] = v["$ref"].split("/")[-1]
        out.append(row)
        walk_props(schema, v, p, out, defs, seen)
    addl = node.get("additionalProperties")
    if isinstance(addl, dict):
        walk_props(schema, addl, "{}.*".format(path) if path else "*", out, defs, seen)
    items = node.get("items")
    if isinstance(items, dict):
        walk_props(schema, items, "{}[]".format(path) if path else "[]", out, defs, seen)


def main(argv=None):
    root = _repo_root()
    schema_dir = root / "src" / "scalim" / "dsl" / "yaml_dsl" / "schema"
    out_dir = root / ".tmp" / "c40-yaml-field-inventory"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Rebuildable; do not commit. Source: demand.gen.json / workflow.gen.json",
        "schemas": {},
    }
    for name in ("demand.gen.json", "workflow.gen.json"):
        schema = json.loads((schema_dir / name).read_text())
        rows = []
        walk_props(schema, schema, "", rows)
        seen = set()
        uniq = []
        for row in rows:
            p = row["path"]
            if p in seen:
                continue
            seen.add(p)
            uniq.append(row)
        payload["schemas"][name] = {"path_count": len(uniq), "paths": uniq}
        slim = {"path_count": len(uniq), "paths": [r["path"] for r in uniq]}
        (out_dir / (name.replace(".gen.json", "") + ".paths.json")).write_text(
            json.dumps(slim, indent=2, ensure_ascii=False) + "\n"
        )
        print("{}: {} paths".format(name, len(uniq)))

    (out_dir / "all.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    (out_dir / "README.md").write_text(
        "# c40 schema path export\n\n"
        "Rebuildable under `.tmp/`; **do not commit**.\n\n"
        "```bash\n"
        "uv run python llmanspec/changes/c40-yaml-runtime-policy-boundary/export_schema_paths.py\n"
        "```\n"
    )
    print("wrote", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
