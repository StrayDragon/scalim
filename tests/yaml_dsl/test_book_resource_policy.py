from scalim.dsl.yaml_dsl._internal.workflow_compile_outputs import effective_write_defaults, validate_xlsx_memory_align_by
from scalim.dsl.yaml_dsl.book_resource_policy import (
    BookResourcePolicy,
    BookWriteAlignBy,
    BookWriteHeaderPolicy,
    BookWriteMode,
    BookWriteOnConflict,
    BookWriteOnMismatch,
    BookWritePolicy,
    ResourcesPolicy,
    builtin_write_defaults_config,
    materialize_resources_policy_onto_books,
    resolve_write_defaults_config,
)
from scalim.dsl.yaml_dsl.schema_dsl.models import BookConfig, BookWriteDefaultsConfig, DemandConfig, ResourcesConfig
from scalim.vendor.dataclassesx import replace

import pytest


def test_book_write_policy_post_init_rejects_non_enum_fields() -> None:
    with pytest.raises(TypeError, match=r"mode must be a BookWriteMode"):
        _ = BookWritePolicy(mode="sheet")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"align_by must be a BookWriteAlignBy"):
        _ = BookWritePolicy(align_by="field_id")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"header_policy must be a BookWriteHeaderPolicy"):
        _ = BookWritePolicy(header_policy="once")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"on_mismatch must be a BookWriteOnMismatch"):
        _ = BookWritePolicy(on_mismatch="error")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"on_conflict must be a BookWriteOnConflict"):
        _ = BookWritePolicy(on_conflict="error")  # type: ignore[arg-type]


def test_book_resource_policy_post_init_rejects_bad_nested_types() -> None:
    with pytest.raises(TypeError, match=r"write must be a BookWritePolicy"):
        _ = BookResourcePolicy(write="nope")  # type: ignore[arg-type]


def test_resources_policy_normalize_and_lookup() -> None:
    assert ResourcesPolicy(books=None).books is None
    with pytest.raises(TypeError, match=r"books must be a mapping or None"):
        _ = ResourcesPolicy(books=["nope"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"keys must be non-empty"):
        _ = ResourcesPolicy(books={"": BookResourcePolicy()})
    with pytest.raises(TypeError, match=r"must be a BookResourcePolicy"):
        _ = ResourcesPolicy(books={"report": "nope"})  # type: ignore[arg-type]

    policy = ResourcesPolicy(
        books={
            " report ": BookResourcePolicy(
                write=BookWritePolicy(
                    mode=BookWriteMode.APPEND,
                    align_by=BookWriteAlignBy.FIELD_ID,
                    header_policy=BookWriteHeaderPolicy.NEVER,
                    on_mismatch=BookWriteOnMismatch.WARN,
                    on_conflict=BookWriteOnConflict.SKIP,
                ),
            )
        }
    )
    assert "report" in (policy.books or {})
    assert policy.write_policy_for("report").mode is BookWriteMode.APPEND
    assert policy.write_policy_for("missing").mode is BookWriteMode.SHEET


def test_resolve_write_defaults() -> None:
    builtin = builtin_write_defaults_config()
    assert builtin.mode == "sheet"
    resolved = resolve_write_defaults_config(book_id="report", resources_policy=None)
    assert resolved.mode == builtin.mode

    policy = ResourcesPolicy(books={"report": BookResourcePolicy(write=BookWritePolicy(mode=BookWriteMode.APPEND))})
    assert resolve_write_defaults_config(book_id="report", resources_policy=policy).mode == "append"
    assert effective_write_defaults("report", resources_policy=policy).mode == "append"
    assert effective_write_defaults("missing").mode == "sheet"
    validate_xlsx_memory_align_by(
        book=BookConfig(),
        book_id="report",
        effective_defaults=BookWriteDefaultsConfig(mode="sheet", align_by="field_id"),
    )


def test_materialize_resources_policy_onto_books_write_defaults_only() -> None:
    config = DemandConfig(
        name="n",
        resources=ResourcesConfig(
            books={
                "file_book": BookConfig(path="./out"),
                "mem_book": BookConfig(),
            }
        ),
    )
    out = materialize_resources_policy_onto_books(config, None)
    assert out.resources is not None
    assert out.resources.books["file_book"].write_defaults is not None
    assert out.resources.books["mem_book"].write_defaults is not None

    policy = ResourcesPolicy(
        books={
            "mem_book": BookResourcePolicy(write=BookWritePolicy(mode=BookWriteMode.APPEND)),
        }
    )
    out2 = materialize_resources_policy_onto_books(config, policy)
    assert out2.resources is not None
    assert out2.resources.books["mem_book"].write_defaults is not None
    assert out2.resources.books["mem_book"].write_defaults.mode == "append"

    empty = replace(config, resources=None)
    assert materialize_resources_policy_onto_books(empty, policy) is empty
