from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_three_symptom_alerts_are_complete() -> None:
    alerts = yaml.safe_load((ROOT / "config/alert_rules.yaml").read_text(encoding="utf-8"))["alerts"]
    assert len(alerts) == 3
    runbook = (ROOT / "docs/alerts.md").read_text(encoding="utf-8")
    for i, a in enumerate(alerts, start=1):
        for field in ("name", "severity", "condition", "duration", "owner", "slack_channel", "runbook"):
            assert a.get(field) and "TODO" not in str(a[field]), (a["name"], field)
        assert a["type"] == "symptom-based"
        assert a["runbook"].endswith(f"#alert-{i}")
        assert f"## Alert {i}" in runbook
    assert "TODO" not in runbook


def test_slo_error_budget_matches_target() -> None:
    slo = yaml.safe_load((ROOT / "config/slo.yaml").read_text(encoding="utf-8"))["primary_slo"]
    assert round(100 - slo["target_percent"], 6) == slo["error_budget_percent"]
