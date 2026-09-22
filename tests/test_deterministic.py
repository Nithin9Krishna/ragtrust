from __future__ import annotations

from ragtrust.services.deterministic import (
    DeterministicQualityEngine,
    compute_text_hash,
    normalize_text,
)


def test_normalize_text_and_hashing():
    t1 = "All suspected incidents must be reported to the SOC within 60 minutes."
    t2 = "ALL SUSPECTED INCIDENTS MUST BE REPORTED TO THE SOC WITHIN 60 MINUTES!!!"
    assert normalize_text(t1) == normalize_text(t2)
    assert compute_text_hash(t1) == compute_text_hash(t2)


def test_detect_exact_duplicates():
    items = [
        {"id": "c1", "question": "What is the password requirement?"},
        {"id": "c2", "question": "What is the password requirement?"},  # duplicate
        {"id": "c3", "question": "How long are logs retained?"},
    ]
    dupes, rate = DeterministicQualityEngine.detect_exact_duplicates(items)
    assert dupes == ["c2"]
    assert round(rate, 2) == 0.33


def test_detect_semantic_duplicates():
    items = [
        {"id": "c1", "question": "What password length is required for standard accounts?"},
        {"id": "c2", "question": "What password length is mandatory for standard corporate accounts?"},
        {"id": "c3", "question": "Describe the encryption protocol for cloud data at rest."},
    ]
    pairs = DeterministicQualityEngine.detect_semantic_duplicates(items, threshold=0.70)
    assert len(pairs) >= 1
    assert pairs[0]["item_1_id"] == "c1"
    assert pairs[0]["item_2_id"] == "c2"


def test_validate_citations():
    valid = {"doc1:p1", "doc1:p2", "doc2:sec1"}
    ok, inv = DeterministicQualityEngine.validate_citations(["doc1:p1", "doc2:sec1"], valid)
    assert ok is True
    assert inv == []

    bad_ok, bad_inv = DeterministicQualityEngine.validate_citations(["doc1:p1", "doc99:bad"], valid)
    assert bad_ok is False
    assert "doc99:bad" in bad_inv


def test_faithfulness_and_factual_f1():
    # 3 supported out of 4 total claims
    faith = DeterministicQualityEngine.calculate_faithfulness(3, 4)
    assert faith == 0.75

    # TP=3, FP=1 (1 unsupported claim), FN=0 (all 3 required facts present)
    f1_res = DeterministicQualityEngine.calculate_factual_f1(tp=3, fp=1, fn=0)
    assert f1_res["precision"] == 0.75
    assert f1_res["recall"] == 1.0
    assert 0.85 < f1_res["f1"] < 0.86


def test_jensen_shannon_divergence():
    target = {"Access": 0.5, "Data": 0.5}
    identical = {"Access": 0.5, "Data": 0.5}
    assert DeterministicQualityEngine.compute_jensen_shannon_divergence(target, identical) == 0.0

    skewed = {"Access": 0.9, "Data": 0.1}
    jsd = DeterministicQualityEngine.compute_jensen_shannon_divergence(target, skewed)
    assert 0.0 < jsd < 0.6


def test_topic_coverage():
    generated = ["Access", "Access", "Data", "Security"]
    quotas = {"Access": 2, "Data": 2, "Security": 1}
    cov = DeterministicQualityEngine.evaluate_topic_coverage(generated, quotas)
    # Access: met (2/2), Data: not met (1/2), Security: met (1/1) -> 2/3 met
    assert cov["met_topics"] == 2
    assert cov["total_topics"] == 3
    assert round(cov["coverage_ratio"], 2) == 0.67
