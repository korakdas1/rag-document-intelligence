from research_assistant.api.errors import error_from_domain, public_message
from research_assistant.core.errors import IngestionError
from research_assistant.core.resource import (
    RESOURCE_EXHAUSTED_CODE,
    looks_like_resource_exhaustion,
    sanitize_public_error,
)


def test_cuda_oom_is_classified() -> None:
    raw = (
        "CUDA out of memory. Tried to allocate 2.00 GiB "
        "(GPU 0; 8.00 GiB total capacity; 7.20 GiB already allocated) "
        "If reserved memory is >> allocated memory try setting "
        "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True"
    )
    assert looks_like_resource_exhaustion(raw)
    public = sanitize_public_error(raw, filename="paper.pdf")
    assert "paper.pdf" in public
    assert "CUDA" not in public
    assert "PyTorch" not in public
    assert "PYTORCH_CUDA_ALLOC_CONF" not in public


def test_api_maps_indexing_oom_to_resource_exhausted() -> None:
    raw = "CUDA out of memory. Tried to allocate 512.00 MiB. PyTorch allocator."
    mapped = error_from_domain(IngestionError(raw, code="indexing_error"))
    assert mapped.code == RESOURCE_EXHAUSTED_CODE
    assert mapped.status_code == 503
    assert "CUDA" not in mapped.message
    assert public_message("indexing_error", raw).startswith("Could not index")
