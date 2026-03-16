from notebooks.marimo.demo_big_data_report.chapters.registry import run_selected_chapters
from scalim_misc.examples.harness import summarize_failures


def test_public_api_mainline_chapters_pass() -> None:
    results = run_selected_chapters(
        chapter_ids=[
            "public_api_dsl_by_yaml",
            "public_api_spec_ir",
            "public_api_planning",
            "public_api_execution",
            "public_api_ob",
            "public_api_hooks_events",
        ]
    )
    failures = summarize_failures(results)
    assert not failures, failures
