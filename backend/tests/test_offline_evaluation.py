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
    assert first["overall"]["status"] == "PASS"
    assert {"conversation", "file_retrieval", "hybrid", "citations", "engineering"}.issubset(first)
    assert first["file_retrieval"]["metrics"] == {
        "hit@1": 1.0, "hit@3": 1.0, "hit@5": 1.0,
        "recall@1": 1.0, "recall@3": 1.0, "recall@5": 1.0, "mrr": 1.0,
    }
    assert first["engineering"]["status"] == "PASS"
    assert "Overall: PASS" in format_report(first)
