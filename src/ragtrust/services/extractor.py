from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from ..schemas import GoldenExampleCreate, SourceMapping


def compute_sha256(content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class SourceExtractor:
    @staticmethod
    def parse_golden_file(
        content: str | bytes,
        filename: str,
        mapping: SourceMapping | None = None,
        role: str = "seed",
    ) -> list[GoldenExampleCreate]:
        mapping = mapping or SourceMapping()
        if isinstance(content, bytes):
            text = content.decode("utf-8", errors="replace")
        else:
            text = content

        examples: list[GoldenExampleCreate] = []

        if filename.endswith(".jsonl") or filename.endswith(".json"):
            # Check if JSON array or JSON lines
            stripped = text.strip()
            if stripped.startswith("["):
                items = json.loads(stripped)
                for idx, row in enumerate(items):
                    q = row.get(mapping.question_col, "").strip()
                    a = row.get(mapping.answer_col, "").strip()
                    if not q or not a:
                        continue
                    ext_id = str(row.get(mapping.id_col or "id", f"seed-{idx+1}"))
                    t = str(row.get(mapping.topic_col or "topic", "general"))
                    ev = row.get(mapping.evidence_col or "evidence_ref")
                    examples.append(
                        GoldenExampleCreate(
                            external_id=ext_id,
                            question=q,
                            trusted_answer=a,
                            topic=t,
                            evidence_ref=str(ev) if ev else None,
                            benchmark_role=role,
                            metadata_json={k: v for k, v in row.items() if k not in {mapping.question_col, mapping.answer_col}},
                        )
                    )
            else:
                for idx, line in enumerate(stripped.splitlines()):
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    q = row.get(mapping.question_col, "").strip()
                    a = row.get(mapping.answer_col, "").strip()
                    if not q or not a:
                        continue
                    ext_id = str(row.get(mapping.id_col or "id", f"seed-{idx+1}"))
                    t = str(row.get(mapping.topic_col or "topic", "general"))
                    ev = row.get(mapping.evidence_col or "evidence_ref")
                    examples.append(
                        GoldenExampleCreate(
                            external_id=ext_id,
                            question=q,
                            trusted_answer=a,
                            topic=t,
                            evidence_ref=str(ev) if ev else None,
                            benchmark_role=role,
                            metadata_json={k: v for k, v in row.items() if k not in {mapping.question_col, mapping.answer_col}},
                        )
                    )
        else:
            # Default CSV parser
            reader = csv.DictReader(io.StringIO(text))
            for idx, row in enumerate(reader):
                q = row.get(mapping.question_col, "").strip()
                a = row.get(mapping.answer_col, "").strip()
                if not q or not a:
                    continue
                ext_id = str(row.get(mapping.id_col or "id", f"seed-{idx+1}"))
                t = str(row.get(mapping.topic_col or "topic", "general"))
                ev = row.get(mapping.evidence_col or "evidence_ref")
                examples.append(
                    GoldenExampleCreate(
                        external_id=ext_id,
                        question=q,
                        trusted_answer=a,
                        topic=t,
                        evidence_ref=str(ev) if ev else None,
                        benchmark_role=role,
                        metadata_json={k: v for k, v in row.items() if k not in {mapping.question_col, mapping.answer_col}},
                    )
                )

        return examples

    @staticmethod
    def extract_text_segments(
        content: str | bytes,
        filename: str,
        asset_id: str,
        chunk_size: int = 600,
    ) -> list[dict[str, Any]]:
        segments: list[dict[str, Any]] = []

        if filename.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(content if isinstance(content, bytes) else content.encode("utf-8")))
            for page_num, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
                if not paragraphs:
                    paragraphs = [page_text.strip()] if page_text.strip() else []
                for p_idx, para in enumerate(paragraphs, start=1):
                    segments.append(
                        {
                            "source_asset_id": asset_id,
                            "locator": f"{filename}:p{page_num}:para{p_idx}",
                            "modality": "text",
                            "text": para,
                            "start_seconds": None,
                            "end_seconds": None,
                            "metadata_json": {"page": page_num, "paragraph": p_idx, "filename": filename},
                        }
                    )
        elif filename.lower().endswith((".vtt", ".srt", ".transcript.txt", ".video.json", ".json")):
            # Video transcript extractor with timestamps
            text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
            if filename.lower().endswith(".json"):
                data = json.loads(text)
                items = data.get("segments") or data.get("transcript")
                if items:
                    for item in items:
                        start = float(item.get("start", 0.0))
                        end = float(item.get("end", 0.0))
                        if end <= start:
                            raise ValueError(f"Invalid media timestamp range: start={start}, end={end}")
                        seg_text = item.get("text", "").strip()
                        speaker = item.get("speaker", "Speaker")
                        locator = f"{filename}:{int(start//60):02d}:{int(start%60):02d}-{int(end//60):02d}:{int(end%60):02d}"
                        segments.append(
                            {
                                "source_asset_id": asset_id,
                                "locator": locator,
                                "modality": "video",
                                "text": f"[{speaker}] {seg_text}",
                                "start_seconds": start,
                                "end_seconds": end,
                                "metadata_json": {"speaker": speaker, "keyframe": item.get("keyframe")},
                            }
                        )
                    return segments
                for item in data.get("segments", data.get("transcript", [])):
                    start = float(item.get("start", 0.0))
                    end = float(item.get("end", 0.0))
                    if end <= start:
                        raise ValueError(f"Invalid media timestamp range: start={start}, end={end}")
                    seg_text = item.get("text", "").strip()
                    speaker = item.get("speaker", "Speaker")
                    locator = f"{filename}:{int(start//60):02d}:{int(start%60):02d}-{int(end//60):02d}:{int(end%60):02d}"
                    segments.append(
                        {
                            "source_asset_id": asset_id,
                            "locator": locator,
                            "modality": "video",
                            "text": f"[{speaker}] {seg_text}",
                            "start_seconds": start,
                            "end_seconds": end,
                            "metadata_json": {"speaker": speaker, "keyframe": item.get("keyframe")},
                        }
                    )
            else:
                # Regex for timestamp patterns: [00:15 - 00:45] Text or 00:00:15 --> 00:00:45
                pattern = re.compile(r"\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\s*[-–>]+\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\]?\s*(.*)")
                lines = text.splitlines()
                current_start = 0.0
                current_end = 15.0
                for idx, line in enumerate(lines):
                    line_s = line.strip()
                    if not line_s:
                        continue
                    m = pattern.match(line_s)
                    if m:
                        g = m.groups()
                        # start sec
                        s1, s2, s3 = g[0], g[1], g[2]
                        current_start = float(s1) * 60 + float(s2) if not s3 else float(s1) * 3600 + float(s2) * 60 + float(s3)
                        # end sec
                        e1, e2, e3 = g[3], g[4], g[5]
                        current_end = float(e1) * 60 + float(e2) if not e3 else float(e1) * 3600 + float(e2) * 60 + float(e3)
                        body = g[6].strip()
                    else:
                        body = line_s
                    if body:
                        locator = f"{filename}:{int(current_start//60):02d}:{int(current_start%60):02d}-{int(current_end//60):02d}:{int(current_end%60):02d}"
                        segments.append(
                            {
                                "source_asset_id": asset_id,
                                "locator": locator,
                                "modality": "video",
                                "text": body,
                                "start_seconds": current_start,
                                "end_seconds": current_end,
                                "metadata_json": {"line": idx + 1},
                            }
                        )
                        current_start = current_end
                        current_end += 15.0
        else:
            # Markdown or text file
            text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p_idx, para in enumerate(paragraphs, start=1):
                segments.append(
                    {
                        "source_asset_id": asset_id,
                        "locator": f"{filename}:sec{p_idx}",
                        "modality": "text",
                        "text": para,
                        "start_seconds": None,
                        "end_seconds": None,
                        "metadata_json": {"section": p_idx, "filename": filename},
                    }
                )

        return segments
