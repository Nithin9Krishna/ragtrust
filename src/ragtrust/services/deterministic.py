from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Any, Sequence


def normalize_text(text: str) -> str:
    """Normalize text for consistent hashing and comparisons."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_text_hash(text: str) -> str:
    """Canonical content hash of normalized text."""
    norm = normalize_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def compute_char_ngrams(text: str, n: int = 3) -> Counter[str]:
    """Compute character n-grams of normalized text."""
    norm = normalize_text(text)
    if len(norm) < n:
        return Counter([norm]) if norm else Counter()
    return Counter(norm[i : i + n] for i in range(len(norm) - n + 1))


def compute_cosine_similarity(vec1: Counter[str], vec2: Counter[str]) -> float:
    """Cosine similarity between two frequency vectors."""
    if not vec1 or not vec2:
        return 0.0
    common = set(vec1.keys()) & set(vec2.keys())
    dot = sum(vec1[k] * vec2[k] for k in common)
    mag1 = math.sqrt(sum(v * v for v in vec1.values()))
    mag2 = math.sqrt(sum(v * v for v in vec2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return float(dot / (mag1 * mag2))


class DeterministicQualityEngine:
    @staticmethod
    def detect_exact_duplicates(items: Sequence[dict[str, Any]], text_key: str = "question") -> tuple[list[str], float]:
        """
        Returns list of duplicate item IDs and the duplication rate.
        """
        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for item in items:
            item_id = item.get("id", "")
            raw = item.get(text_key, "")
            h = compute_text_hash(raw)
            if h in seen:
                duplicates.append(item_id)
            else:
                seen[h] = item_id
        rate = len(duplicates) / len(items) if items else 0.0
        return duplicates, round(rate, 4)

    @staticmethod
    def detect_semantic_duplicates(
        items: Sequence[dict[str, Any]],
        threshold: float = 0.82,
        text_key: str = "question",
    ) -> list[dict[str, Any]]:
        """
        Detects pairs of near-duplicate items exceeding the cosine similarity threshold.
        """
        vectors = [compute_char_ngrams(item.get(text_key, "")) for item in items]
        pairs = []
        n = len(items)
        for i in range(n):
            for j in range(i + 1, n):
                sim = compute_cosine_similarity(vectors[i], vectors[j])
                if sim >= threshold:
                    pairs.append(
                        {
                            "item_1_id": items[i].get("id", f"idx_{i}"),
                            "item_2_id": items[j].get("id", f"idx_{j}"),
                            "similarity": round(sim, 4),
                            "text_1": items[i].get(text_key, "")[:100],
                            "text_2": items[j].get(text_key, "")[:100],
                        }
                    )
        return pairs

    @staticmethod
    def validate_citations(
        evidence_refs: list[str],
        valid_locators: set[str],
    ) -> tuple[bool, list[str]]:
        """
        Verifies that every cited evidence reference matches an existing segment locator.
        """
        if not evidence_refs:
            return False, ["Missing evidence references"]
        invalid = [ref for ref in evidence_refs if ref not in valid_locators]
        return len(invalid) == 0, invalid

    @staticmethod
    def calculate_faithfulness(supported_claims: int, total_claims: int) -> float:
        """
        Faithfulness = supported factual claims / total factual claims.
        Handles zero factual claims by returning 1.0 (no unsupported claims).
        """
        if total_claims <= 0:
            return 1.0
        return round(supported_claims / total_claims, 4)

    @staticmethod
    def calculate_factual_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
        """
        Computes claim-level precision, recall, and F1.
        """
        precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
        recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    @staticmethod
    def compute_jensen_shannon_divergence(
        target_dist: dict[str, float],
        actual_dist: dict[str, float],
    ) -> float:
        """
        Computes Jensen-Shannon divergence between target and actual distributions.
        Returns a value in [0.0, 1.0]. Lower means closer alignment.
        """
        keys = set(target_dist.keys()) | set(actual_dist.keys())
        if not keys:
            return 0.0

        # Normalize distributions to sum to 1.0
        sum_t = sum(target_dist.values()) or 1.0
        sum_a = sum(actual_dist.values()) or 1.0

        p = {k: target_dist.get(k, 0.0) / sum_t for k in keys}
        q = {k: actual_dist.get(k, 0.0) / sum_a for k in keys}
        m = {k: 0.5 * (p[k] + q[k]) for k in keys}

        def kl_div(dist_a: dict[str, float], dist_b: dict[str, float]) -> float:
            kl = 0.0
            for k in keys:
                val_a = dist_a[k]
                val_b = dist_b[k]
                if val_a > 0 and val_b > 0:
                    kl += val_a * math.log2(val_a / val_b)
            return kl

        jsd = 0.5 * kl_div(p, m) + 0.5 * kl_div(q, m)
        return round(math.sqrt(max(0.0, jsd)), 4)  # Return JS Distance (bounded [0, 1])

    @staticmethod
    def evaluate_topic_coverage(
        generated_topics: list[str],
        topic_quotas: dict[str, int],
    ) -> dict[str, Any]:
        """
        Measures topic counts versus target quotas.
        """
        counts = Counter(generated_topics)
        met_quotas = 0
        total_targets = len(topic_quotas)
        breakdown = {}

        for topic, quota in topic_quotas.items():
            actual = counts.get(topic, 0)
            met = actual >= quota
            if met:
                met_quotas += 1
            breakdown[topic] = {
                "target": quota,
                "actual": actual,
                "met": met,
                "deficit": max(0, quota - actual),
            }

        coverage_ratio = met_quotas / total_targets if total_targets > 0 else 1.0
        return {
            "coverage_ratio": round(coverage_ratio, 4),
            "met_topics": met_quotas,
            "total_topics": total_targets,
            "breakdown": breakdown,
        }
