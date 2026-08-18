from app.retrieval.experiments.models import QueryRewriteComparisonReport


def recommendation(report: QueryRewriteComparisonReport) -> str:
    """Return a conservative integration recommendation for one benchmark report."""
    summary = report.summary
    metrics_non_decreasing = (
        summary.hit_rate_delta >= 0.0
        and summary.recall_delta >= 0.0
        and summary.reciprocal_rank_delta >= 0.0
    )
    observable_benefit = (
        summary.hit_rate_delta > 0.0
        or summary.recall_delta > 0.0
        or summary.reciprocal_rank_delta > 0.0
        or summary.improved_case_count > 0
    )
    if (
        metrics_non_decreasing
        and observable_benefit
        and summary.improved_case_count > summary.regressed_case_count
    ):
        return "INTEGRATE"
    return "DO NOT INTEGRATE YET"


def format_report(report: QueryRewriteComparisonReport) -> str:
    """Render the benchmark's intentionally short, non-sensitive console output."""
    lines = ["Local query rewrite benchmark"]
    for comparison in report.case_comparisons:
        lines.append(
            " | ".join(
                [
                    comparison.case_id,
                    f"original={comparison.original_query}",
                    f"rewritten={comparison.rewritten_query}",
                    f"changed={str(comparison.rewrite_changed).lower()}",
                    (
                        "baseline="
                        f"H@{report.k}:{comparison.baseline.hit_rate_at_k:.3f},"
                        f"R@{report.k}:{comparison.baseline.recall_at_k:.3f},"
                        f"MRR:{comparison.baseline.reciprocal_rank:.3f}"
                    ),
                    (
                        "rewritten="
                        f"H@{report.k}:{comparison.rewritten.hit_rate_at_k:.3f},"
                        f"R@{report.k}:{comparison.rewritten.recall_at_k:.3f},"
                        f"MRR:{comparison.rewritten.reciprocal_rank:.3f}"
                    ),
                    f"classification={comparison.outcome}",
                ]
            )
        )
    summary = report.summary
    lines.extend(
        [
            (
                "Aggregate: "
                f"cases={summary.evaluated_case_count}, "
                f"rewrite_changed={sum(item.rewrite_changed for item in report.case_comparisons)}, "
                f"improved={summary.improved_case_count}, "
                f"unchanged={summary.unchanged_case_count}, "
                f"regressed={summary.regressed_case_count}"
            ),
            (
                "Hit Rate: "
                f"{summary.baseline_mean_hit_rate_at_k:.3f} -> "
                f"{summary.rewritten_mean_hit_rate_at_k:.3f} "
                f"(delta {summary.hit_rate_delta:+.3f})"
            ),
            (
                "Recall: "
                f"{summary.baseline_mean_recall_at_k:.3f} -> "
                f"{summary.rewritten_mean_recall_at_k:.3f} "
                f"(delta {summary.recall_delta:+.3f})"
            ),
            (
                "MRR: "
                f"{summary.baseline_mean_reciprocal_rank:.3f} -> "
                f"{summary.rewritten_mean_reciprocal_rank:.3f} "
                f"(delta {summary.reciprocal_rank_delta:+.3f})"
            ),
            f"Decision: {recommendation(report)}",
        ]
    )
    return "\n".join(lines)
