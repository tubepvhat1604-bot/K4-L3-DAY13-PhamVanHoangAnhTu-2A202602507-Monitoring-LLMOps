from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def _post(headers: dict | None = None, message: str = "Explain monitoring") -> httpx.Response:
    async def go() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/chat",
                headers=headers or {},
                json={"user_id": "u1", "session_id": "s1", "feature": "qa", "message": message},
            )

    return asyncio.run(go())


def _events(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_generates_valid_correlation_id_and_headers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "l.jsonl")
    r = _post()
    cid = r.headers["x-request-id"]
    assert cid.startswith("req-") and len(cid) == 12
    assert r.json()["correlation_id"] == cid
    assert int(r.headers["x-response-time-ms"]) >= 0


def test_honours_incoming_request_id_and_rejects_bad_one(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "l.jsonl")
    assert _post({"x-request-id": "req-abcdef12"}).headers["x-request-id"] == "req-abcdef12"
    bad = _post({"x-request-id": "evil\nid"}).headers["x-request-id"]
    assert bad != "evil\nid" and bad.startswith("req-")


def test_logs_are_enriched_and_do_not_leak_between_requests(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "l.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    a = _post({"x-request-id": "req-aaaaaaaa"})
    b = _post({"x-request-id": "req-bbbbbbbb"})
    assert a.status_code == b.status_code == 200
    for rec in (e for e in _events(log_path) if e.get("service") == "api"):
        assert {"user_id_hash", "session_id", "feature", "model", "env"} <= rec.keys()
        assert rec["correlation_id"] in {"req-aaaaaaaa", "req-bbbbbbbb"}
    # mỗi correlation id chỉ xuất hiện đúng 2 event api (received + sent)
    ids = [e["correlation_id"] for e in _events(log_path) if e.get("service") == "api"]
    assert ids.count("req-aaaaaaaa") == 2 and ids.count("req-bbbbbbbb") == 2


def test_pii_is_scrubbed_before_hitting_the_file(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "l.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    _post(message="mail a@b.com sdt 0901234567 cccd 012345678901 the 4111 1111 1111 1111")
    raw = log_path.read_text(encoding="utf-8")
    for leaked in ("a@b.com", "0901234567", "012345678901", "4111 1111 1111 1111"):
        assert leaked not in raw
    assert "REDACTED_EMAIL" in raw
