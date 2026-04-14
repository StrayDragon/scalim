import contextlib
import io
import logging

from scalim.events._events import RelationLookupEvent
from scalim.ob.presets.relations import RelationConfig, RelationObserver
from scalim.ob.structured_logging import install_jsonl_logging


@contextlib.contextmanager
def _installed_jsonl(buf: io.StringIO):
    root = logging.getLogger("scalim")
    orig_handlers = list(root.handlers)
    orig_level = int(root.level)
    orig_propagate = bool(root.propagate)
    try:
        root.handlers[:] = [h for h in root.handlers if getattr(h, "name", "") != "scalim.jsonl"]
        install_jsonl_logging(stream=buf, profile="compact")
        yield
    finally:
        root.handlers[:] = orig_handlers
        root.setLevel(orig_level)
        root.propagate = orig_propagate


def test_relations_type_error_and_samples_are_structured_under_jsonl() -> None:
    buf = io.StringIO()
    with _installed_jsonl(buf):
        logger = logging.getLogger("scalim.tests.relations")
        obs = RelationObserver(
            config=RelationConfig(
                enabled=True,
                log_type_mismatch=True,
                sampling_rate=1.0,
                report_format="console",
                logger=logger,
            )
        )

        # generate type mismatch samples
        for i in range(3):
            obs.on_relation_lookup(
                RelationLookupEvent(
                    field_key="x",
                    row_id=i,
                    fk_raw="1",
                    fk_normalized=1,
                    target_source="customers",
                    result="type_error",
                    fk_type="str",
                    expected_type="int",
                    error_message="bad type",
                )
            )

        obs.print_summary()
        obs.close()
        obs.close()

    assert buf.getvalue()
