import inspect
import os

import scalim.execution.executor.batch as batch_pkg
import scalim.execution.executor.helpers as helpers_pkg
import scalim.execution.executor.runtime as runtime_pkg
import scalim.execution.pipeline.base as pipeline_base_pkg
from scalim.execution.executor.batch.executor import BatchExecutor
from scalim.execution.executor.helpers.field_access import extract_field
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.base.pipeline import Pipeline, SeqPipeline
from scalim.utils.relation_signature import build_relation_signature


def _assert_defined_outside_init(obj: object) -> None:
    source = inspect.getsourcefile(obj)
    assert source is not None
    assert os.path.basename(source) != "__init__.py"


def test_execution_impl_is_not_in_init_modules() -> None:
    _assert_defined_outside_init(BatchExecutor)
    _assert_defined_outside_init(ExecutionRuntime)
    _assert_defined_outside_init(Pipeline)
    _assert_defined_outside_init(SeqPipeline)
    _assert_defined_outside_init(extract_field)
    _assert_defined_outside_init(build_relation_signature)


def test_execution_init_packages_do_not_reexport_symbols() -> None:
    assert not hasattr(batch_pkg, "BatchExecutor")
    assert not hasattr(runtime_pkg, "ExecutionRuntime")
    assert not hasattr(pipeline_base_pkg, "Pipeline")
    assert not hasattr(pipeline_base_pkg, "SeqPipeline")
    assert not hasattr(helpers_pkg, "extract_field")
    assert not hasattr(helpers_pkg, "build_relation_signature")
