from notebooks.marimo.example_hooks_events_scenarios.chapters.registry import run_selected_chapters
from scalim_misc.examples.harness import summarize_failures


def test_hooks_events_scenario_chapters_pass() -> None:
    results = run_selected_chapters(
        chapter_ids=[
            "ch010_post_export_upload",
            "ch020_precheck_route_sync_async",
            "ch030_upload_retry",
            "ch040_pre_use_batch_size",
            "ch050_workflow_viz_finished",
        ]
    )
    failures = summarize_failures(results)
    assert not failures, failures
