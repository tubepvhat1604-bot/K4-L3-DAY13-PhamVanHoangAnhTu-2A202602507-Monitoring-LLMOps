from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

# Định dạng hợp lệ: req-<8 ký tự hex>. Header sai format bị bỏ qua để tránh
# log injection hoặc ID quá dài/khó truy vết.
_VALID_ID = re.compile(r"^req-[0-9a-f]{8}$")


def new_correlation_id() -> str:
    return f"req-{uuid.uuid4().hex[:8]}"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Xóa context của request trước để tránh rò rỉ giữa các request.
        clear_contextvars()

        incoming = (request.headers.get("x-request-id") or "").strip()
        correlation_id = incoming if _VALID_ID.match(incoming) else new_correlation_id()

        bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)

        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = str(int((time.perf_counter() - start) * 1000))

        return response
