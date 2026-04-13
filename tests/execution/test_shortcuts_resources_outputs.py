from pathlib import Path

import pytest


def _publish_versioned_outputs(
    output_root: Path,
    *,
    run_id: str,
    book_ids: tuple[str, ...] = (),
    file_ids: tuple[str, ...] = (),
) -> None:
    from scalim.execution import versioned_outputs

    layout = versioned_outputs.ensure_output_root_layout(output_root)
    _ = versioned_outputs.ensure_version_dir(layout, version_id=str(run_id))

    books = {bid: versioned_outputs.book_output_relpath(book_id=bid) for bid in book_ids}
    files = {fid: versioned_outputs.file_output_relpath(file_id=fid) for fid in file_ids}

    for bid in book_ids:
        path = versioned_outputs.book_output_path(layout, version_id=str(run_id), book_id=bid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"dummy-xlsx")

    for fid in file_ids:
        path = versioned_outputs.file_output_path(layout, version_id=str(run_id), file_id=fid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x,y\n1,2\n", encoding="utf-8")

    _ = versioned_outputs.write_version_manifest(layout, version_id=str(run_id), books=books, files=files)
    _ = versioned_outputs.update_latest(
        layout,
        version_id=str(run_id),
        version_manifest_relpath=versioned_outputs.version_manifest_relpath(version_id=str(run_id)),
    )


def test_load_latest_outputs_happy_path_books_and_files(tmp_path: Path) -> None:
    from scalim.execution import versioned_outputs
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    run_id = "r1"
    _publish_versioned_outputs(output_root, run_id=run_id, book_ids=("report",), file_ids=("detail",))

    latest = outputs.load_latest_outputs(output_root)
    assert latest.run_id == run_id
    assert latest.books["report"] == versioned_outputs.book_output_path(
        versioned_outputs.ensure_output_root_layout(output_root), version_id=run_id, book_id="report"
    )
    assert latest.files["detail"] == versioned_outputs.file_output_path(
        versioned_outputs.ensure_output_root_layout(output_root), version_id=run_id, file_id="detail"
    )

    assert outputs.latest_book_path(output_root, book_id="report") == latest.books["report"]
    assert outputs.latest_file_path(output_root, file_id="detail") == latest.files["detail"]


def test_load_latest_outputs_supports_only_books(tmp_path: Path) -> None:
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    _publish_versioned_outputs(output_root, run_id="r1", book_ids=("report",), file_ids=())

    latest = outputs.load_latest_outputs(output_root)
    assert "report" in latest.books
    assert latest.files == {}


def test_load_latest_outputs_supports_only_files(tmp_path: Path) -> None:
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    _publish_versioned_outputs(output_root, run_id="r1", book_ids=(), file_ids=("detail",))

    latest = outputs.load_latest_outputs(output_root)
    assert latest.books == {}
    assert "detail" in latest.files


def test_try_load_latest_outputs_returns_none_when_latest_is_missing(tmp_path: Path) -> None:
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    output_root.mkdir(parents=True, exist_ok=True)

    assert outputs.try_load_latest_outputs(output_root) is None
    with pytest.raises(FileNotFoundError, match="Latest outputs pointer not found"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_fails_on_invalid_latest_json(tmp_path: Path) -> None:
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    latest_path = output_root / "manifest" / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse latest outputs pointer"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_fails_on_invalid_version_manifest_json(tmp_path: Path) -> None:
    from scalim.execution import versioned_outputs
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    (output_root / "manifest").mkdir(parents=True, exist_ok=True)
    (output_root / "versions" / "r1").mkdir(parents=True, exist_ok=True)

    (output_root / "manifest" / "latest.json").write_text(
        '{{"version_id":"r1","version_manifest_relpath":"{}"}}'.format(versioned_outputs.version_manifest_relpath(version_id="r1")),
        encoding="utf-8",
    )
    (output_root / "versions" / "r1" / "manifest.json").write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse version manifest"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_fails_when_manifest_points_to_missing_artifact(tmp_path: Path) -> None:
    from scalim.execution import versioned_outputs
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    layout = versioned_outputs.ensure_output_root_layout(output_root)
    _ = versioned_outputs.ensure_version_dir(layout, version_id="r1")

    _ = versioned_outputs.write_version_manifest(
        layout,
        version_id="r1",
        books={"report": versioned_outputs.book_output_relpath(book_id="report")},
        files={},
    )
    _ = versioned_outputs.update_latest(
        layout,
        version_id="r1",
        version_manifest_relpath=versioned_outputs.version_manifest_relpath(version_id="r1"),
    )

    with pytest.raises(FileNotFoundError, match="Latest outputs manifest points to missing artifacts"):
        _ = outputs.load_latest_outputs(output_root)


def test_try_load_latest_outputs_returns_latest_when_present(tmp_path: Path) -> None:
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    _publish_versioned_outputs(output_root, run_id="r1", book_ids=("report",), file_ids=("detail",))

    latest = outputs.try_load_latest_outputs(output_root)
    assert latest is not None
    assert latest.run_id == "r1"


def test_load_latest_outputs_fails_when_latest_json_is_not_an_object(tmp_path: Path) -> None:
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    latest_path = output_root / "manifest" / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="must be a JSON object"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_fails_when_latest_pointer_missing_required_fields(tmp_path: Path) -> None:
    from scalim.execution import versioned_outputs
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    latest_path = output_root / "manifest" / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(
        '{{"version_manifest_relpath":"{}"}}'.format(versioned_outputs.version_manifest_relpath(version_id="r1")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required field"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_fails_on_unsafe_version_manifest_relpath(tmp_path: Path) -> None:
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    latest_path = output_root / "manifest" / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text('{"version_id":"r1","version_manifest_relpath":"../oops.json"}', encoding="utf-8")

    with pytest.raises(ValueError, match="version_manifest_relpath must be a safe relative path"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_fails_on_absolute_version_manifest_relpath(tmp_path: Path) -> None:
    import json

    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    latest_path = output_root / "manifest" / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)

    abs_manifest = str((tmp_path / "abs_manifest.json").resolve())
    latest_path.write_text(
        '{{"version_id":"r1","version_manifest_relpath":{}}}'.format(json.dumps(abs_manifest)),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="version_manifest_relpath must be a safe relative path"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_fails_when_version_manifest_is_missing(tmp_path: Path) -> None:
    from scalim.execution import versioned_outputs
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    latest_path = output_root / "manifest" / "latest.json"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(
        '{{"version_id":"r1","version_manifest_relpath":"{}"}}'.format(versioned_outputs.version_manifest_relpath(version_id="r1")),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="version manifest not found"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_handles_missing_books_and_files_fields(tmp_path: Path) -> None:
    from scalim.execution import versioned_outputs
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    (output_root / "manifest").mkdir(parents=True, exist_ok=True)
    (output_root / "versions" / "r1").mkdir(parents=True, exist_ok=True)

    (output_root / "manifest" / "latest.json").write_text(
        '{{"version_id":"r1","version_manifest_relpath":"{}"}}'.format(versioned_outputs.version_manifest_relpath(version_id="r1")),
        encoding="utf-8",
    )
    (output_root / "versions" / "r1" / "manifest.json").write_text('{"version_id":"r1"}', encoding="utf-8")

    latest = outputs.load_latest_outputs(output_root)
    assert latest.books == {}
    assert latest.files == {}


def test_load_latest_outputs_fails_when_manifest_books_is_not_an_object(tmp_path: Path) -> None:
    from scalim.execution import versioned_outputs
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    (output_root / "manifest").mkdir(parents=True, exist_ok=True)
    (output_root / "versions" / "r1").mkdir(parents=True, exist_ok=True)

    (output_root / "manifest" / "latest.json").write_text(
        '{{"version_id":"r1","version_manifest_relpath":"{}"}}'.format(versioned_outputs.version_manifest_relpath(version_id="r1")),
        encoding="utf-8",
    )
    (output_root / "versions" / "r1" / "manifest.json").write_text('{"version_id":"r1","books":[],"files":{}}', encoding="utf-8")

    with pytest.raises(TypeError, match="Invalid version manifest"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_fails_on_unsafe_artifact_relpaths_in_manifest(tmp_path: Path) -> None:
    from scalim.execution import versioned_outputs
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    (output_root / "manifest").mkdir(parents=True, exist_ok=True)
    (output_root / "versions" / "r1").mkdir(parents=True, exist_ok=True)

    (output_root / "manifest" / "latest.json").write_text(
        '{{"version_id":"r1","version_manifest_relpath":"{}"}}'.format(versioned_outputs.version_manifest_relpath(version_id="r1")),
        encoding="utf-8",
    )
    (output_root / "versions" / "r1" / "manifest.json").write_text(
        '{"version_id":"r1","books":{"report":"../oops.xlsx"},"files":{}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid version manifest relpath"):
        _ = outputs.load_latest_outputs(output_root)


def test_load_latest_outputs_skips_empty_relpaths(tmp_path: Path) -> None:
    from scalim.execution import versioned_outputs
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    (output_root / "manifest").mkdir(parents=True, exist_ok=True)
    (output_root / "versions" / "r1").mkdir(parents=True, exist_ok=True)

    (output_root / "manifest" / "latest.json").write_text(
        '{{"version_id":"r1","version_manifest_relpath":"{}"}}'.format(versioned_outputs.version_manifest_relpath(version_id="r1")),
        encoding="utf-8",
    )
    (output_root / "versions" / "r1" / "manifest.json").write_text('{"version_id":"r1","books":{"report":""},"files":{}}', encoding="utf-8")

    latest = outputs.load_latest_outputs(output_root)
    assert latest.books == {}


def test_latest_id_shortcuts_fail_fast_on_empty_or_missing_ids(tmp_path: Path) -> None:
    from scalim.shortcuts.resources import outputs

    output_root = tmp_path / "out"
    _publish_versioned_outputs(output_root, run_id="r1", book_ids=("report",), file_ids=("detail",))

    with pytest.raises(ValueError, match="book_id must be a non-empty string"):
        _ = outputs.latest_book_path(output_root, book_id="")
    with pytest.raises(ValueError, match="file_id must be a non-empty string"):
        _ = outputs.latest_file_path(output_root, file_id="")

    with pytest.raises(KeyError, match="missing book_id"):
        _ = outputs.latest_book_path(output_root, book_id="missing")
    with pytest.raises(KeyError, match="missing file_id"):
        _ = outputs.latest_file_path(output_root, file_id="missing")


def test_parse_id_to_paths_rejects_non_string_ids(tmp_path: Path) -> None:
    from scalim.shortcuts.resources import outputs

    with pytest.raises(TypeError, match="id must be a string"):
        _ = outputs._parse_id_to_paths(  # noqa: SLF001  # intentional branch coverage
            {1: "books/report.xlsx"},
            kind="books",
            base_dir=tmp_path,
            manifest_path=tmp_path / "manifest.json",
            output_root=tmp_path,
        )
