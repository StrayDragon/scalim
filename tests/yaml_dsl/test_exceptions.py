from scalim.exceptions import REDACTED_ERROR_MESSAGE, safe_error_message


def test_safe_error_message_redacts_when_str_raises() -> None:
    class BadStrError(Exception):
        def __str__(self) -> str:
            raise RuntimeError("boom")

    assert safe_error_message(BadStrError()) == REDACTED_ERROR_MESSAGE
