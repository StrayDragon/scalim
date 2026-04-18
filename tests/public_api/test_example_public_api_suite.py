from notebooks.marimo.example_public_api_suite.chapters.registry import run_selected_chapters
from scalim_misc.examples.harness import summarize_failures


def test_public_api_mainline_chapters_pass() -> None:
    results = run_selected_chapters(
        chapter_ids=[
            "ch130_public_api_dsl_by_yaml",
            "ch150_public_api_planning",
            "ch160_public_api_execution",
            "ch165_public_api_resources",
            "ch170_public_api_ob",
            "ch180_public_api_hooks_events",
            "ch182_public_api_event_type_groups",
            "ch184_public_api_sinks_pandas",
        ]
    )
    failures = summarize_failures(results)
    assert not failures, failures
