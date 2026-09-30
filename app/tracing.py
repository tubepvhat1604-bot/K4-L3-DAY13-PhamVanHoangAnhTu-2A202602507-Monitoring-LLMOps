from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

class _NoopObservation:
    """Thay thế observation khi SDK không có; nhận và bỏ qua mọi update."""

    def update(self, **kwargs: Any) -> None:
        return None


@contextmanager
def _noop_observation():
    yield _NoopObservation()


try:
    from langfuse import get_client, observe, propagate_attributes

    LANGFUSE_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - chỉ dùng khi chưa cài requirements
    LANGFUSE_SDK_AVAILABLE = False

    def observe(*args: Any, **kwargs: Any):
        def decorator(func):
            return func

        return decorator

    class _DummyClient:
        def update_current_span(self, **kwargs: Any) -> None:
            return None

        def update_current_generation(self, **kwargs: Any) -> None:
            return None

        def start_as_current_observation(self, **kwargs: Any):
            return _noop_observation()

    def get_client():
        return _DummyClient()

    @contextmanager
    def propagate_attributes(**kwargs: Any):
        yield


def get_langfuse_client():
    return get_client()


@contextmanager
def start_observation(name: str, as_type: str = "span", **kwargs: Any):
    """Mở một child observation (retriever/generation/span...) dưới observation hiện tại.

    Khi Langfuse chưa cấu hình key, client của SDK tự vô hiệu hóa nên context
    manager này vẫn chạy bình thường và không gửi gì đi.
    """
    client = get_client()
    with client.start_as_current_observation(name=name, as_type=as_type, **kwargs) as observation:
        yield observation


def tracing_enabled() -> bool:
    return LANGFUSE_SDK_AVAILABLE and bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )
