from __future__ import annotations

from typing import Any, Callable

from ..schemas import CalibrationResult


class EvaluatorCalibrationEngine:
    @staticmethod
    def compute_cohens_kappa(tp: int, tn: int, fp: int, fn: int) -> float:
        total = tp + tn + fp + fn
        if total == 0:
            return 1.0

        # Observed agreement
        p_o = (tp + tn) / total

        # Expected agreement by chance
        # Positive predicted = tp + fp, Positive actual = tp + fn
        # Negative predicted = tn + fn, Negative actual = tn + fp
        p_pred_pos = (tp + fp) / total
        p_act_pos = (tp + fn) / total
        p_pred_neg = (tn + fn) / total
        p_act_neg = (tn + fp) / total

        p_e = (p_pred_pos * p_act_pos) + (p_pred_neg * p_act_neg)

        if p_e >= 1.0:
            return 1.0
        kappa = (p_o - p_e) / (1.0 - p_e)
        return round(max(-1.0, min(1.0, kappa)), 4)

    @classmethod
    def evaluate_benchmark(
        cls,
        benchmark_cases: list[dict[str, Any]],
        evaluator_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> CalibrationResult:
        """
        Runs the evaluator against calibration cases with human-verified ground truth.
        Positive class = Defective case.
        Negative class = Correct/Valid case.
        """
        tp = 0  # Actual Defective, Detected as Defective (rejected/needs_revision)
        fp = 0  # Actual Correct, Flagged as Defective
        tn = 0  # Actual Correct, Passed as Correct (accepted)
        fn = 0  # Actual Defective, Passed as Correct (missed defect)

        details = []

        for case in benchmark_cases:
            # Expected label: "defective" or "correct"
            expected_defective = case.get("is_defective", False)
            eval_output = evaluator_fn(case)

            # Evaluator suggests rejected or needs_revision for defective
            status = eval_output.get("suggested_status", "accepted")
            predicted_defective = status in {"rejected", "needs_revision", "needs_review"}

            if expected_defective and predicted_defective:
                tp += 1
                outcome = "TP (Defect Detected)"
            elif not expected_defective and not predicted_defective:
                tn += 1
                outcome = "TN (Correct Approved)"
            elif not expected_defective and predicted_defective:
                fp += 1
                outcome = "FP (False Alarm)"
            else:
                fn += 1
                outcome = "FN (Missed Defect)"

            details.append(
                {
                    "case_id": case.get("id"),
                    "question": case.get("question"),
                    "defect_type": case.get("defect_type", "none"),
                    "expected_defective": expected_defective,
                    "predicted_status": status,
                    "outcome": outcome,
                    "reason": eval_output.get("concise_reason", ""),
                }
            )

        total = len(benchmark_cases)
        accuracy = (tp + tn) / total if total > 0 else 1.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
        recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        kappa = cls.compute_cohens_kappa(tp, tn, fp, fn)

        return CalibrationResult(
            total_cases=total,
            accuracy=round(accuracy, 4),
            defect_precision=round(precision, 4),
            defect_recall=round(recall, 4),
            defect_f1=round(f1, 4),
            cohens_kappa=kappa,
            confusion_matrix={"TP": tp, "TN": tn, "FP": fp, "FN": fn},
            details=details,
        )
