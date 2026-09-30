"""Sinh dashboard HTML tĩnh 6 panel từ data/logs.jsonl theo config/dashboard.yaml.

Chạy:  python scripts/build_dashboard.py [--minutes 60] [--out dashboard.html]
Mở dashboard.html bằng trình duyệt để chụp evidence 11-dashboard-overview.png.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.metrics import percentile  # noqa: E402

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"


def load_records(path: Path, since: datetime | None) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            rec["_dt"] = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        if since is None or rec["_dt"] >= since:
            out.append(rec)
    return out


def by_minute(records: list[dict], field: str | None = None) -> dict[str, float]:
    buckets: dict[str, float] = defaultdict(float)
    for r in records:
        key = r["_dt"].strftime("%H:%M")
        buckets[key] += 1 if field is None else (r.get(field) or 0)
    return dict(sorted(buckets.items()))


def compute(records: list[dict], minutes: int) -> dict:
    sent = [r for r in records if r.get("event") == "response_sent"]
    received = [r for r in records if r.get("event") == "request_received"]
    failed = [r for r in records if r.get("event") == "request_failed"]
    lat = [r["latency_ms"] for r in sent if r.get("latency_ms") is not None]
    ttft = [r["ttft_ms"] for r in sent if r.get("ttft_ms") is not None]
    tools = [r for r in records if r.get("tool_success") is not None]
    err_breakdown: dict[str, int] = defaultdict(int)
    for r in failed:
        err_breakdown[r.get("error_type") or "unknown"] += 1
    quality = [r["quality_score"] for r in sent if r.get("quality_score") is not None]
    return {
        "p50": percentile(lat, 50), "p95": percentile(lat, 95), "p99": percentile(lat, 99),
        "ttft_p95": percentile(ttft, 95),
        "lat_series": {
            m: percentile([r["latency_ms"] for r in sent if r["_dt"].strftime("%H:%M") == m], 95)
            for m in by_minute(sent)
        },
        "requests": len(received),
        "rate_per_min": round(len(received) / max(minutes, 1), 2),
        "traffic_series": by_minute(received),
        "error_rate": round(len(failed) / len(received) * 100, 2) if received else 0.0,
        "errors": dict(err_breakdown),
        "retrieval_success": round(sum(1 for r in tools if r["tool_success"]) / len(tools) * 100, 2) if tools else 100.0,
        "cost_total": round(sum(r.get("cost_usd") or 0 for r in sent), 4),
        "cost_series": by_minute(sent, "cost_usd"),
        "tokens_in": sum(r.get("tokens_in") or 0 for r in sent),
        "tokens_out": sum(r.get("tokens_out") or 0 for r in sent),
        "quality": round(sum(quality) / len(quality), 3) if quality else 0.0,
        "quality_series": {
            m: round(sum(x) / len(x), 3)
            for m, x in ((m, [r["quality_score"] for r in sent if r["_dt"].strftime("%H:%M") == m and r.get("quality_score") is not None]) for m in by_minute(sent))
            if x
        },
    }


def ok(value: float, op: str, limit: float) -> bool:
    return value <= limit if op == "lte" else value >= limit


def bars(series: dict[str, float], limit: float | None = None, w: int = 420, h: int = 110) -> str:
    if not series:
        return '<div class="empty">Chưa có dữ liệu trong time range</div>'
    top = max(list(series.values()) + ([limit] if limit else [])) or 1
    n = len(series)
    bw = max(4, (w - 30) / n - 3)
    parts = [f'<svg viewBox="0 0 {w} {h + 20}" class="chart">']
    for i, (k, v) in enumerate(series.items()):
        bh = v / top * h
        x = 30 + i * ((w - 30) / n)
        parts.append(f'<rect x="{x:.1f}" y="{h - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="#4f7cff"><title>{k}: {v}</title></rect>')
        if n <= 12 or i % max(1, n // 8) == 0:
            parts.append(f'<text x="{x:.1f}" y="{h + 14}" font-size="9" fill="#888">{k}</text>')
    if limit:
        y = h - limit / top * h
        parts.append(f'<line x1="30" x2="{w}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5484d" stroke-dasharray="4 3"/>')
        parts.append(f'<text x="32" y="{max(y - 3, 9):.1f}" font-size="9" fill="#e5484d">threshold {limit}</text>')
    parts.append(f'<text x="0" y="10" font-size="9" fill="#888">{top:g}</text></svg>')
    return "".join(parts)


def panel(cfg: dict, headline: str, status: bool, detail: str, chart: str) -> str:
    th = cfg["threshold"]
    op = "≤" if th["operator"] == "lte" else "≥"
    badge = "ok" if status else "bad"
    return (
        f'<section class="panel"><h2>{html.escape(cfg["title"])}</h2>'
        f'<div class="big {badge}">{headline}</div>'
        f'<div class="sub">{detail}</div>{chart}'
        f'<div class="foot">Threshold/SLO: {th["aggregation"]} {op} {th["value"]} {cfg["unit"]} '
        f'<span class="pill {badge}">{"OK" if status else "VI PHẠM"}</span></div></section>'
    )


def render(cfg: dict, m: dict, minutes: int, now: datetime) -> str:
    P = {p["id"]: p for p in cfg["panels"]}
    th = lambda pid: P[pid]["threshold"]
    panels = [
        panel(P["latency"], f'P95 {m["p95"]:.0f} ms',
              ok(m["p95"], th("latency")["operator"], th("latency")["value"]),
              f'P50 {m["p50"]:.0f} ms · P95 {m["p95"]:.0f} ms · P99 {m["p99"]:.0f} ms · TTFT P95 {m["ttft_p95"]:.0f} ms',
              bars(m["lat_series"], th("latency")["value"])),
        panel(P["traffic"], f'{m["requests"]} req',
              ok(m["rate_per_min"], th("traffic")["operator"], th("traffic")["value"]),
              f'{m["rate_per_min"]} requests/phút (trung bình {minutes} phút)',
              bars(m["traffic_series"])),
        panel(P["errors"], f'{m["error_rate"]}% error',
              ok(m["error_rate"], th("errors")["operator"], th("errors")["value"]),
              f'Retrieval success {m["retrieval_success"]}% · breakdown: {m["errors"] or "không có lỗi"}',
              bars({k: float(v) for k, v in m["errors"].items()})),
        panel(P["cost"], f'${m["cost_total"]}',
              ok(m["cost_total"], th("cost")["operator"], th("cost")["value"]),
              "Tổng chi phí (USD) trong time range", bars(m["cost_series"], None)),
        panel(P["tokens"], f'{m["tokens_in"] + m["tokens_out"]:,} tokens',
              ok(max(m["tokens_in"], m["tokens_out"]), th("tokens")["operator"], th("tokens")["value"]),
              f'input {m["tokens_in"]:,} · output {m["tokens_out"]:,}',
              bars({"input": float(m["tokens_in"]), "output": float(m["tokens_out"])}, th("tokens")["value"])),
        panel(P["quality"], f'{m["quality"]}',
              ok(m["quality"], th("quality")["operator"], th("quality")["value"]),
              "Quality proxy trung bình (0–1)", bars(m["quality_series"], th("quality")["value"])),
    ]
    style = """
    body{font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:20px}
    h1{font-size:18px;margin:0 0 4px}.meta{color:#888;font-size:12px;margin-bottom:16px}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:14px}
    .panel{background:#181b22;border:1px solid #2a2e38;border-radius:10px;padding:14px}
    h2{font-size:13px;margin:0 0 6px;color:#aab}.big{font-size:26px;font-weight:700}
    .ok{color:#3ecf8e}.bad{color:#e5484d}.sub{font-size:12px;color:#99a;margin:2px 0 8px}
    .chart{width:100%;height:auto}.empty{color:#666;font-size:12px;padding:20px 0}
    .foot{font-size:11px;color:#889;margin-top:6px}.pill{padding:1px 7px;border-radius:9px;font-size:10px;color:#fff}
    .pill.ok{background:#1f8f5f;color:#fff}.pill.bad{background:#b3262b;color:#fff}
    """
    return (
        f'<!doctype html><html lang="vi"><meta charset="utf-8"><title>{html.escape(cfg["title"])}</title>'
        f'<style>{style}</style><h1>{html.escape(cfg["title"])}</h1>'
        f'<div class="meta">Nguồn: data/logs.jsonl · time range: {minutes} phút gần nhất · '
        f'refresh {cfg["refresh_seconds"]}s · tạo lúc {now.astimezone().strftime("%Y-%m-%d %H:%M:%S")}</div>'
        f'<meta http-equiv="refresh" content="{cfg["refresh_seconds"]}">'
        f'<div class="grid">{"".join(panels)}</div></html>'
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "dashboard.html")
    ap.add_argument("--log", type=Path, default=LOG_PATH)
    args = ap.parse_args()
    if not args.log.exists():
        print(f"Không thấy {args.log}. Chạy API và load_test trước.")
        return 1
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    now = datetime.now(timezone.utc)
    records = load_records(args.log, now - timedelta(minutes=args.minutes))
    m = compute(records, args.minutes)
    args.out.write_text(render(cfg, m, args.minutes, now), encoding="utf-8")
    print(f"Đã ghi {args.out} từ {len(records)} log records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
