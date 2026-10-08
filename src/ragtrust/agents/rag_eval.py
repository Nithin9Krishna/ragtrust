from __future__ import annotations

import ipaddress
import json
import socket
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from ..schemas import RagEvalRequest, RagEvalSummary
from .base import BaseAgent


MAX_ENDPOINT_RESPONSE_BYTES = 1024 * 1024
ENDPOINT_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class _PinnedEndpoint:
    url: httpx.URL
    hostname: str
    host_header: str


def _resolve_public_endpoint(url: str) -> _PinnedEndpoint:
    try:
        if not isinstance(url, str) or any(ord(char) <= 32 or ord(char) == 127 for char in url) or "\\" in url:
            raise ValueError("Invalid endpoint URL")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443)):
            raise ValueError("Invalid endpoint URL")
        endpoint = httpx.URL(url)
        hostname = endpoint.raw_host.decode("ascii")
        if not hostname or "%" in hostname:
            raise ValueError("Invalid endpoint hostname")
    except (ValueError, UnicodeError, httpx.InvalidURL) as exc:
        raise ValueError("RAG endpoint must be a public HTTPS URL on port 443 without embedded credentials") from exc

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            resolved = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
            addresses = [ipaddress.ip_address(item[4][0]) for item in resolved]
        except (OSError, ValueError, UnicodeError) as exc:
            raise ValueError("RAG endpoint hostname could not be resolved") from exc
    else:
        addresses = [literal]
    if not addresses or any(not address.is_global or address.is_multicast or address.is_reserved for address in addresses):
        raise ValueError("Private or loopback RAG endpoints are not allowed in this deployment")
    # The request URL contains only this validated literal address. DNS changes
    # cannot change the destination between validation and any later case.
    return _PinnedEndpoint(
        url=endpoint.copy_with(host=str(addresses[0]), fragment=None),
        hostname=hostname,
        host_header=endpoint.netloc.decode("ascii"),
    )


def validate_public_endpoint(url: str) -> None:
    _resolve_public_endpoint(url)


def _endpoint_answer(endpoint: _PinnedEndpoint, question: str) -> str:
    deadline = time.monotonic() + ENDPOINT_TIMEOUT_SECONDS
    with httpx.Client(
        trust_env=False, verify=True, follow_redirects=False,
        timeout=httpx.Timeout(ENDPOINT_TIMEOUT_SECONDS, connect=5.0, pool=5.0),
    ) as client:
        with client.stream(
            "POST", endpoint.url, json={"query": question},
            headers={"Host": endpoint.host_header, "Accept-Encoding": "identity"},
            # httpcore uses this name for both TLS SNI and certificate checking,
            # while its TCP connection uses the pinned IP from the request URL.
            extensions={"sni_hostname": endpoint.hostname},
        ) as response:
            response.raise_for_status()
            if response.headers.get("content-encoding", "identity").strip().lower() != "identity":
                raise ValueError("Endpoint must return an uncompressed response")
            content_length = response.headers.get("content-length")
            if content_length is not None and int(content_length) > MAX_ENDPOINT_RESPONSE_BYTES:
                raise ValueError("Endpoint response exceeds the 1 MiB limit")
            body = bytearray()
            for chunk in response.iter_raw():
                if time.monotonic() > deadline:
                    raise httpx.ReadTimeout("Endpoint response exceeded its time limit")
                if len(body) + len(chunk) > MAX_ENDPOINT_RESPONSE_BYTES:
                    raise ValueError("Endpoint response exceeds the 1 MiB limit")
                body.extend(chunk)
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Endpoint response must be a JSON object")
            answer = payload.get("answer", payload.get("response"))
            if not isinstance(answer, str):
                raise ValueError("Endpoint response must contain a string answer or response")
            return answer


class RagEvaluationAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="RagEvaluationAgent", role="Optional RAG response capture and comparison")

    def run(self, inputs: dict[str, Any], mode: str = "fixture") -> dict[str, Any]:
        start = time.time()
        cases = inputs.get("cases", [])
        config: RagEvalRequest = inputs.get("config") or RagEvalRequest()
        if not config.endpoint_url and not config.mock_responses and not config.demo_mode:
            raise ValueError("Provide an endpoint or recorded responses, or explicitly select fixture demonstration")
        endpoint = _resolve_public_endpoint(config.endpoint_url) if config.endpoint_url else None
        evaluation_mode = "live_endpoint" if config.endpoint_url else "fixture" if config.demo_mode else "recorded"
        results, overlaps = [], []
        correct_abstentions = total_abstentions = errors = 0
        for case in cases:
            question, reference = case.get("question", ""), case.get("candidate_reference_answer", "")
            req_start = time.time()
            error = None
            answer = ""
            try:
                if endpoint:
                    answer = _endpoint_answer(endpoint, question)
                elif question in config.mock_responses:
                    answer = config.mock_responses[question]
                elif config.demo_mode:
                    answer = reference
                else:
                    raise ValueError("No recorded response for this question")
            except (httpx.HTTPError, OSError, ValueError, TypeError) as exc:
                error = f"{type(exc).__name__}: response could not be evaluated"
                errors += 1
            overlap = None
            if not error:
                reference_tokens = set(reference.lower().split())
                overlap = len(reference_tokens & set(answer.lower().split())) / len(reference_tokens) if reference_tokens else None
                if overlap is not None:
                    overlaps.append(overlap)
                if case.get("expected_behavior") == "abstain":
                    total_abstentions += 1
                    correct_abstentions += any(term in answer.lower() for term in ["not have sufficient", "not specify", "cannot answer", "no information", "does not provide"])
            results.append({
                "case_id": case.get("id"), "question": question,
                "reference_answer": reference, "deployed_system_answer": answer,
                "latency_ms": round((time.time() - req_start) * 1000, 2),
                "reference_token_recall": round(overlap, 4) if overlap is not None else None,
                "faithfulness": None, "relevance": None, "error": error,
                "evaluation_mode": evaluation_mode,
            })
        summary = RagEvalSummary(
            total_cases_evaluated=len(cases) - errors, errors=errors,
            avg_reference_token_recall=sum(overlaps) / len(overlaps) if overlaps else None,
            abstention_accuracy=correct_abstentions / total_abstentions if total_abstentions else None,
            avg_latency_ms=sum(item["latency_ms"] for item in results) / len(results) if results else 0,
            evaluation_mode=evaluation_mode, results=results,
            limitations=[
                "Reference token recall is lexical overlap, not factual accuracy or faithfulness.",
                "Semantic answer quality and retrieval metrics are not assessed by this adapter.",
                "Fixture responses copy the reference solely to demonstrate the workflow." if evaluation_mode == "fixture" else "Abstention detection uses a documented phrase heuristic.",
            ],
        )
        self.record_usage((time.time() - start) * 1000, tokens_est=0)
        return summary.model_dump()
