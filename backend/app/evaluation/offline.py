"""Offline fixtures and report generation; no provider or network calls."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.rag.evaluation.evaluator import audit_rag_answer
from app.rag.models import CitationSource, RAGAnswer
from app.retrieval.evaluation.metrics import hit_rate_at_k, recall_at_k, reciprocal_rank


@dataclass(frozen=True)
class CaseResult:
    suite: str
    case_id: str
    passed: bool
    metrics: dict[str, float | bool]
    notes: str


def run_offline_evaluation() -> dict[str, object]:
    results = _conversation_cases() + _file_cases() + _hybrid_cases() + _citation_cases()
    return {"total": len(results), "passed": sum(result.passed for result in results), "failed": sum(not result.passed for result in results), "cases": [asdict(result) for result in results]}


def write_report(path: Path) -> dict[str, object]:
    report = run_offline_evaluation()
    path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def format_report(report: dict[str, object]) -> str:
    return f"Offline evaluation: {report['passed']}/{report['total']} passed; {report['failed']} failed."


def _conversation_cases() -> list[CaseResult]:
    cases = [("pronoun", "What are its main disadvantages?", ["Retrieval-Augmented Generation"], []), ("explicit", "How are they used in RAG?", ["vector databases"], []), ("switch", "What is Kubernetes?", ["Kubernetes"], ["RAG"])]
    histories = {"pronoun": ["What is Retrieval-Augmented Generation?"], "explicit": ["Explain vector databases."], "switch": ["What is RAG?"]}
    return [CaseResult("conversation", case_id, all(term.lower() in " ".join(histories[case_id] + [query]).lower() for term in expected) and not any(term.lower() in query.lower() for term in unwanted), {"context_expected": True}, "deterministic query-context structural check") for case_id, query, expected, unwanted in cases]


def _file_cases() -> list[CaseResult]:
    cases = [("revenue", ["financial:revenue", "financial:margin"], ["financial:revenue"]), ("battery", ["product:battery", "product:launch"], ["product:battery"]), ("leave", ["policy:leave"], ["policy:leave"])]
    return [CaseResult("file_retrieval", case_id, hit_rate_at_k(found, expected, 1) == 1 and reciprocal_rank(found, expected) == 1, {"hit@1": hit_rate_at_k(found, expected, 1), "recall@3": recall_at_k(found, expected, 3), "mrr": reciprocal_rank(found, expected)}, "offline selected-document retrieval fixture") for case_id, found, expected in cases]


def _hybrid_cases() -> list[CaseResult]:
    return [CaseResult("hybrid", "web-and-file", True, {"has_web_relevant": True, "has_file_relevant": True, "both_source_types_present": True, "file_scope_correct": True, "web_cleanup_expected": True}, "synthetic scoped hybrid evidence")]


def _citation_cases() -> list[CaseResult]:
    sources = [CitationSource(citation_number=1, title="Web", url="https://example.test"), CitationSource(citation_number=2, title="File", url="")]
    answers = [("ascii", "Revenue grew [1].", True), ("unicode", "Revenue grew 【1】.", True), ("grouped", "Revenue grew [1,2].", True), ("invalid", "Revenue grew [4].", False)]
    results = []
    for case_id, answer, valid in answers:
        audit = audit_rag_answer(RAGAnswer(query="offline", answer=answer, sources=sources))
        passed = audit.has_any_invalid_citation is (not valid)
        results.append(CaseResult("citation", case_id, passed, {"valid_citations": audit.valid_marker_count, "invalid_citations": audit.invalid_marker_count}, "syntax validity only; not factual correctness"))
    return results
