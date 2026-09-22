from __future__ import annotations

from ragtrust.services.extractor import SourceExtractor, compute_sha256


def test_parse_golden_csv():
    csv_data = """id,question,answer,topic
1,What is MFA?,Multi factor auth,Security
2,What is TLS?,Transport layer security,Encryption
"""
    parsed = SourceExtractor.parse_golden_file(csv_data, "test.csv")
    assert len(parsed) == 2
    assert parsed[0].question == "What is MFA?"
    assert parsed[0].trusted_answer == "Multi factor auth"
    assert parsed[0].topic == "Security"


def test_parse_golden_jsonl():
    jsonl_data = """{"id": "j1", "question": "Q1", "answer": "A1", "topic": "T1"}
{"id": "j2", "question": "Q2", "answer": "A2", "topic": "T2"}
"""
    parsed = SourceExtractor.parse_golden_file(jsonl_data, "test.jsonl")
    assert len(parsed) == 2
    assert parsed[1].question == "Q2"


def test_extract_text_segments():
    text = "Paragraph 1 content.\n\nParagraph 2 content."
    segs = SourceExtractor.extract_text_segments(text, "sample.txt", asset_id="asset-1")
    assert len(segs) == 2
    assert segs[0]["locator"] == "sample.txt:sec1"
    assert segs[1]["locator"] == "sample.txt:sec2"


def test_extract_video_segments():
    video_json = """{
      "segments": [
        {"start": 0.0, "end": 25.0, "speaker": "Alice", "text": "Welcome to security training."},
        {"start": 25.0, "end": 50.0, "speaker": "Bob", "text": "Passwords must be strong."}
      ]
    }"""
    segs = SourceExtractor.extract_text_segments(video_json, "video.json", asset_id="vid-1")
    assert len(segs) == 2
    assert segs[0]["modality"] == "video"
    assert segs[0]["start_seconds"] == 0.0
    assert segs[0]["end_seconds"] == 25.0
    assert "video.json:00:00-00:25" in segs[0]["locator"]


def test_compute_sha256():
    h = compute_sha256("test content")
    assert len(h) == 64
    assert compute_sha256("test content") == h
