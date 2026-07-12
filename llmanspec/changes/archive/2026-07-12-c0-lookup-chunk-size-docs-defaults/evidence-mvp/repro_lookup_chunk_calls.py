#!/usr/bin/env python3
"""Pinned evidence: lookup_chunk_size call-count contract.

Output: .tmp/evidence/lookup-chunk-size-docs/<ts>/result.json
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _opts(modules: List[str]):
    from scalim.dsl.yaml_dsl.runtime.contracts import (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunSecurityOptions,
    )

    return DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(modules)),
        outputs=DemandRunOutputOptions(capture=CaptureRows()),
    )


def _run(*, n_keys: int, chunk_size: object) -> Dict[str, Any]:
    from scalim.dsl.yaml_dsl import run

    calls = {"n": 0, "keys_seen": 0}
    mod = types.ModuleType("tests.tmp_chunk_evidence_loaders")

    def load_main(**kwargs):  # type: ignore[no-untyped-def]
        return [{"id": i, "ref_id": i % max(1, n_keys)} for i in range(n_keys)]

    def load_ref(*, ids=None, **kwargs):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        key_list = list(ids or [])
        calls["keys_seen"] += len(key_list)
        return {k: {"ref_id": k, "val": k} for k in key_list}

    mod.load_main = load_main  # type: ignore[attr-defined]
    mod.load_ref = load_ref  # type: ignore[attr-defined]
    sys.modules["tests.tmp_chunk_evidence_loaders"] = mod

    tmp = Path(tempfile.mkdtemp(prefix="scalim-chunk-ev-"))
    out = tmp / "out"
    out.mkdir()
    chunk_yaml = ""
    if chunk_size is not None:
        chunk_yaml = "    lookup_chunk_size: {}\n".format(chunk_size)
    demand = tmp / "d.yaml"
    demand.write_text(
        (
            "name: chunk_ev\n"
            "main_source:\n"
            "  source_id: main\n"
            "  loader: tests.tmp_chunk_evidence_loaders:load_main\n"
            "  fields:\n"
            "    id:\n"
            "      extract: id\n"
            "    ref_id:\n"
            "      extract: ref_id\n"
            "sources:\n"
            "  dim:\n"
            "    loader: tests.tmp_chunk_evidence_loaders:load_ref\n"
            "    key: ref_id\n"
            "{chunk}"
            "    params:\n"
            "      ids:\n"
            "        $keys:\n"
            "          as: list\n"
            "    fields:\n"
            "      val:\n"
            "        extract: val\n"
            "        relation:\n"
            "          steps:\n"
            "            - from: main.ref_id\n"
            "              to: dim.ref_id\n"
            "resources:\n"
            "  files:\n"
            "    detail_csv:\n"
            "      csv_file:\n"
            "        path: {out}\n"
            "outputs:\n"
            "  - name: detail\n"
            "    to:\n"
            "      file: detail_csv\n"
            "    fields: [id, ref_id, val]\n"
        ).format(chunk=chunk_yaml, out=str(out)),
        encoding="utf-8",
    )
    _ = run(str(demand), options=_opts(["tests.tmp_chunk_evidence_loaders"]))
    expected = 1
    if isinstance(chunk_size, int) and chunk_size > 0 and chunk_size < n_keys:
        expected = (n_keys + chunk_size - 1) // chunk_size
    return {
        "n_keys": n_keys,
        "chunk_size": chunk_size,
        "loader_calls": calls["n"],
        "keys_seen": calls["keys_seen"],
        "expected_calls": expected,
        "ok": calls["n"] == expected,
    }


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(os.path.join(".tmp", "evidence", "lookup-chunk-size-docs", ts))
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = [
        _run(n_keys=300, chunk_size=None),
        _run(n_keys=300, chunk_size=0),
        _run(n_keys=300, chunk_size=40),
        _run(n_keys=500, chunk_size=25),
    ]
    report = {
        "topic": "lookup-chunk-size-docs",
        "pinned_script": str(Path(__file__).as_posix()),
        "cases": cases,
        "all_ok": all(c["ok"] for c in cases),
    }
    path = out_dir / "result.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_ok": report["all_ok"], "cases": cases}, ensure_ascii=False, indent=2, sort_keys=True))
    print("report -> {}".format(path))
    if not report["all_ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
