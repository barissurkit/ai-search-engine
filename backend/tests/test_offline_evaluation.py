import json

from app.evaluation.offline import format_report, run_offline_evaluation, write_report


def test_offline_evaluation_is_deterministic_and_passing(tmp_path):
    first = run_offline_evaluation()
    assert first == run_offline_evaluation()
    assert first["failed"] == 0
    assert first["passed"] == first["total"]
    report_path = tmp_path / "report.json"
    assert write_report(report_path) == first
    assert json.loads(report_path.read_text()) == first
    assert "passed" in format_report(first)
