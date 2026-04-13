from pathlib import Path

import pytest

from scalim.execution import versioned_outputs as mod


def test_validate_version_id_rejects_unsafe_values() -> None:
    with pytest.raises(ValueError, match=r"safe path segment"):
        _ = mod.validate_version_id("")

    with pytest.raises(ValueError, match=r"safe path segment"):
        _ = mod.validate_version_id("..")


def test_output_id_validators_reject_unsafe_values() -> None:
    with pytest.raises(ValueError, match=r"file_id must be a safe path segment"):
        _ = mod.file_output_relpath(file_id="bad/id")

    with pytest.raises(ValueError, match=r"book_id must be a safe path segment"):
        _ = mod.book_output_relpath(book_id="bad:id")


def test_update_latest_requires_non_empty_relpath(tmp_path: Path) -> None:
    layout = mod.ensure_output_root_layout(tmp_path / "out")
    with pytest.raises(ValueError, match=r"version_manifest_relpath must be a non-empty string"):
        _ = mod.update_latest(layout, version_id="v1", version_manifest_relpath="")


def test_parse_versioned_output_path_rejects_invalid_shapes(tmp_path: Path) -> None:
    root = tmp_path / "out"

    with pytest.raises(ValueError, match=r"missing 'versions'"):
        _ = mod.parse_versioned_output_path(root / "detail.csv")

    with pytest.raises(ValueError, match=r"Invalid versioned output path shape"):
        _ = mod.parse_versioned_output_path(root / "versions" / "v1" / "books")

    with pytest.raises(ValueError, match=r"Invalid versioned book output filename"):
        _ = mod.parse_versioned_output_path(root / "versions" / "v1" / "books" / "bad.csv")

    with pytest.raises(ValueError, match=r"Invalid versioned file output filename"):
        _ = mod.parse_versioned_output_path(root / "versions" / "v1" / "files" / "bad.xlsx")

    with pytest.raises(ValueError, match=r"Unknown versioned output kind"):
        _ = mod.parse_versioned_output_path(root / "versions" / "v1" / "unknown" / "x.txt")


def test_write_version_manifest_cleans_temp_path_on_replace_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    removed = []

    def _boom(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    def _record_remove(temp_path: str):  # type: ignore[no-untyped-def]
        removed.append(temp_path)

    monkeypatch.setattr(mod, "atomic_replace_temp_path", _boom)
    monkeypatch.setattr(mod, "best_effort_remove_temp_path", _record_remove)

    layout = mod.ensure_output_root_layout(tmp_path / "out")
    with pytest.raises(RuntimeError, match="boom"):
        _ = mod.write_version_manifest(layout, version_id="v1")

    assert removed
