from notebooks.marimo.demo_big_data_report.chapters_of_scenarios.registry import run_selected_chapters
from scalim_misc.examples.harness import summarize_failures


def test_hooks_events_scenario_chapters_pass() -> None:
    results = run_selected_chapters(
        chapter_ids=[
            "ch210_post_export_upload",
            "ch220_precheck_route_sync_async",
            "ch230_upload_retry",
            "ch240_pre_use_batch_size",
            "ch250_workflow_viz_finished",
        ]
    )
    failures = summarize_failures(results)
    assert not failures, failures
