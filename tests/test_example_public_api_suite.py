from scalim_misc.examples.harness import run_public_api_examples, summarize_failures


def test_public_api_examples_suite() -> None:
    results = run_public_api_examples()
    failures = summarize_failures(results)
    assert not failures, failures
