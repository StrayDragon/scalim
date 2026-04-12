import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scalim.dsl.yaml_dsl.runtime import entrypoints as entrypoints_mod


def _spec(*, targets=(), derived_targets=(), meta_sheet=None, audit_sheet=None):  # type: ignore[no-untyped-def]
    return SimpleNamespace(
        targets=tuple(targets),
        derived_targets=tuple(derived_targets),
        meta_sheet=meta_sheet,
        audit_sheet=audit_sheet,
    )


def _target(path: str | None):  # type: ignore[no-untyped-def]
    return SimpleNamespace(output=SimpleNamespace(path=path))


def test_ensure_versioned_output_dirs_covers_skip_and_meta_audit_paths(tmp_path: Path) -> None:
    root = tmp_path / "out"
    versioned_book_path = str(root / "versions" / "v1" / "books" / "report.xlsx")

    compilation = SimpleNamespace(
        request=SimpleNamespace(
            output_composition=_spec(
                targets=(
                    _target(None),
                    _target(str(tmp_path / "not-versioned.csv")),
                    _target(versioned_book_path),
                ),
                meta_sheet=_target(str(tmp_path / "meta.xlsx")),
                audit_sheet=_target(None),
            )
        )
    )

    entrypoints_mod._ensure_versioned_output_dirs(compilation)  # noqa: SLF001
    assert (root / "versions" / "v1").is_dir()


def test_ensure_versioned_output_dirs_rejects_multiple_version_ids_per_root(tmp_path: Path) -> None:
    root = tmp_path / "out"
    a = str(root / "versions" / "v1" / "files" / "a.csv")
    b = str(root / "versions" / "v2" / "files" / "b.csv")

    compilation = SimpleNamespace(request=SimpleNamespace(output_composition=_spec(targets=(_target(a), _target(b)))))

    with pytest.raises(ValueError, match=r"Multiple version_id values for the same output root"):
        entrypoints_mod._ensure_versioned_output_dirs(compilation)  # noqa: SLF001


def test_update_versioned_output_manifests_writes_manifest_and_latest(tmp_path: Path) -> None:
    root = tmp_path / "out"
    book = str(root / "versions" / "v1" / "books" / "report.xlsx")
    file = str(root / "versions" / "v1" / "files" / "detail.csv")

    result = SimpleNamespace(
        core=SimpleNamespace(
            outputs={
                "book": book,
                "file": file,
                "none": None,
                "non_versioned": str(tmp_path / "other.csv"),
            }
        )
    )

    entrypoints_mod._update_versioned_output_manifests(result)  # noqa: SLF001

    latest = root / "manifest" / "latest.json"
    manifest = root / "versions" / "v1" / "manifest.json"
    assert latest.is_file()
    assert manifest.is_file()

    latest_payload = json.loads(latest.read_text("utf-8"))
    assert latest_payload["version_id"] == "v1"


def test_update_versioned_output_manifests_rejects_multiple_version_ids_per_root(tmp_path: Path) -> None:
    root = tmp_path / "out"
    a = str(root / "versions" / "v1" / "books" / "a.xlsx")
    b = str(root / "versions" / "v2" / "books" / "b.xlsx")

    result = SimpleNamespace(core=SimpleNamespace(outputs={"a": a, "b": b}))

    with pytest.raises(ValueError, match=r"Multiple version_id values for the same output root"):
        entrypoints_mod._update_versioned_output_manifests(result)  # noqa: SLF001
