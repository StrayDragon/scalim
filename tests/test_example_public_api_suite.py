from notebooks.marimo.demo_big_data_report.chapters.registry import run_selected_chapters
from scalim_misc.examples.harness import summarize_failures


def test_public_api_mainline_chapters_pass() -> None:
    results = run_selected_chapters(
        chapter_ids=[
            "ch130_public_api_dsl_by_yaml",
            "ch140_public_api_spec_ir",
            "ch150_public_api_planning",
            "ch160_public_api_execution",
            "ch170_public_api_ob",
            "ch180_public_api_hooks_events",
        ]
    )
    failures = summarize_failures(results)
    assert not failures, failures
