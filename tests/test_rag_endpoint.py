import json
import socket
import ssl

import httpx
import pytest
from httpcore._backends.sync import SyncBackend

from ragtrust.agents import rag_eval
from ragtrust.schemas import RagEvalRequest


def dns_records(*addresses):
    return [
        (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM,
         socket.IPPROTO_TCP, "", (address, 443))
        for address in addresses
    ]


def run_endpoint(url="https://rag.example/answer", questions=("question",)):
    return rag_eval.RagEvaluationAgent().run({
        "cases": [{"id": str(index), "question": question, "candidate_reference_answer": "answer"}
                  for index, question in enumerate(questions)],
        "config": RagEvalRequest(endpoint_url=url),
    })


@pytest.mark.parametrize("addresses", [
    ("127.0.0.1",), ("10.0.0.1",), ("169.254.169.254",), ("::1",),
    ("fc00::1",), ("fe80::1",), ("::ffff:127.0.0.1",),
    ("224.0.0.1",), ("ff02::1",), ("4000::1",), ("100.64.0.1",),
    ("8.8.8.8", "10.0.0.1"), ("2606:4700:4700::1111", "::1"),
    ("8.8.8.8", "fc00::1"), (),
])
def test_rejects_any_non_public_dns_address(monkeypatch, addresses):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: dns_records(*addresses))
    with pytest.raises(ValueError, match="Private or loopback"):
        rag_eval.validate_public_endpoint("https://rag.example/answer")


@pytest.mark.parametrize("url", [
    "http://rag.example", "https://rag.example:8443", "https://rag.example:bad",
    "https://user:secret@rag.example", "https://@rag.example", "https:///answer",
    "https://[::1", "https://rag.example\n/answer", "https://rag.example\\other",
    "https://[2606:4700:4700::1111%25eth0]/answer",
])
def test_rejects_invalid_urls_before_dns(monkeypatch, url):
    def unexpected_dns(*args, **kwargs):
        pytest.fail("Invalid endpoint URL must not be resolved")
    monkeypatch.setattr(socket, "getaddrinfo", unexpected_dns)
    with pytest.raises(ValueError, match="public HTTPS URL on port 443"):
        rag_eval.validate_public_endpoint(url)


def test_dns_errors_are_friendly(monkeypatch):
    def unresolved(*args, **kwargs):
        raise socket.gaierror("sensitive internal resolver details")
    monkeypatch.setattr(socket, "getaddrinfo", unresolved)
    with pytest.raises(ValueError, match="hostname could not be resolved") as error:
        run_endpoint()
    assert "sensitive" not in str(error.value)


@pytest.mark.parametrize("url", ["https://127.0.0.1", "https://[::1]", "https://[::ffff:127.0.0.1]"])
def test_rejects_private_literals_without_dns(monkeypatch, url):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("Literal IP must not use DNS"))
    with pytest.raises(ValueError, match="Private or loopback"):
        rag_eval.validate_public_endpoint(url)


@pytest.mark.parametrize("address", ["8.8.8.8", "2606:4700:4700::1111"])
def test_real_transport_pins_ip_and_preserves_verified_hostname(monkeypatch, address):
    resolutions, connections, tls_calls, writes = [], [], [], []
    def resolve(hostname, port, **kwargs):
        resolutions.append((hostname, port))
        # A hostname lookup after validation would rebind to a local address.
        return dns_records(address) if len(resolutions) == 1 else dns_records("127.0.0.1")
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    # Environment proxies would otherwise bypass destination pinning.
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9999")

    class NetworkStream:
        def __init__(self):
            body = b'{"answer":"answer"}'
            self.response = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body

        def start_tls(self, ssl_context, server_hostname, timeout):
            tls_calls.append((server_hostname, ssl_context.check_hostname, ssl_context.verify_mode))
            assert timeout is not None and timeout <= 5
            return self

        def get_extra_info(self, name):
            return None

        def read(self, max_bytes, timeout):
            assert timeout is not None and timeout <= 15
            data, self.response = self.response[:max_bytes], self.response[max_bytes:]
            return data

        def write(self, buffer, timeout):
            assert timeout is not None and timeout <= 15
            writes.append(buffer)

        def close(self):
            pass

    def connect(self, host, port, **kwargs):
        connections.append((host, port))
        return NetworkStream()
    monkeypatch.setattr(SyncBackend, "connect_tcp", connect)
    result = run_endpoint("https://rag.example:443/answer?kind=test", questions=("first", "second"))
    assert result["total_cases_evaluated"] == 2
    assert resolutions == [("rag.example", 443)]
    assert connections == [(address, 443)] * 2
    assert tls_calls == [("rag.example", True, ssl.CERT_REQUIRED)] * 2
    assert b"Host: rag.example\r\n" in b"".join(writes)
    assert b"POST /answer?kind=test HTTP/1.1" in b"".join(writes)
    assert b'{"query":"first"}' in b"".join(writes)


class Chunks(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.read_count = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk

    def close(self):
        self.closed = True


def use_mock_transport(monkeypatch, handler):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: dns_records("8.8.8.8"))
    actual_client = httpx.Client
    def client(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["verify"] is True
        assert kwargs["follow_redirects"] is False
        return actual_client(transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(rag_eval.httpx, "Client", client)


def test_redirect_is_not_followed(monkeypatch):
    requests = []
    stream = Chunks([b""])
    def respond(request):
        requests.append(request)
        return httpx.Response(307, headers={"location": "https://127.0.0.1/private"}, stream=stream)
    use_mock_transport(monkeypatch, respond)
    result = run_endpoint()
    assert len(requests) == 1
    assert result["errors"] == 1
    assert result["results"][0]["error"] == "HTTPStatusError: response could not be evaluated"
    assert stream.closed


@pytest.mark.parametrize("declared_length", [None, "1048577"])
def test_response_size_cap_stops_streaming(monkeypatch, declared_length):
    stream = Chunks([b"x" * (64 * 1024)] * 17 + [b"must not read"])
    headers = {"content-length": declared_length} if declared_length else {}
    use_mock_transport(monkeypatch, lambda request: httpx.Response(200, headers=headers, stream=stream))
    result = run_endpoint()
    assert result["errors"] == 1
    assert result["total_cases_evaluated"] == 0
    assert stream.read_count == (0 if declared_length else 17)
    assert stream.closed


def test_response_exactly_at_limit_is_accepted(monkeypatch):
    data = json.dumps({"answer": "answer"}).encode()
    stream = Chunks([data, b" " * (rag_eval.MAX_ENDPOINT_RESPONSE_BYTES - len(data))])
    use_mock_transport(monkeypatch, lambda request: httpx.Response(200, stream=stream))
    result = run_endpoint()
    assert result["total_cases_evaluated"] == 1
    assert result["results"][0]["deployed_system_answer"] == "answer"


def test_response_alias_is_accepted(monkeypatch):
    use_mock_transport(monkeypatch, lambda request: httpx.Response(200, stream=Chunks([b'{"response":"answer"}'])))
    result = run_endpoint()
    assert result["total_cases_evaluated"] == 1
    assert result["results"][0]["deployed_system_answer"] == "answer"


def test_compressed_response_cannot_expand_past_cap(monkeypatch):
    stream = Chunks([b"compressed bytes must not be read"])
    use_mock_transport(monkeypatch, lambda request: httpx.Response(200, headers={"content-encoding": "gzip"}, stream=stream))
    result = run_endpoint()
    assert result["errors"] == 1
    assert stream.read_count == 0
    assert stream.closed


@pytest.mark.parametrize("payload", [b"invalid json", b"[]", b'{"answer":null}', b'{"answer":42}', b'"answer"'])
def test_invalid_payload_is_a_case_error(monkeypatch, payload):
    use_mock_transport(monkeypatch, lambda request: httpx.Response(200, stream=Chunks([payload])))
    result = run_endpoint()
    assert result["errors"] == 1
    assert result["total_cases_evaluated"] == 0
    assert result["avg_reference_token_recall"] is None


@pytest.mark.parametrize("error", [httpx.ConnectError("details"), httpx.ReadTimeout("details"), OSError("details")])
def test_network_errors_are_sanitized_per_case(monkeypatch, error):
    def fail(request):
        raise error
    use_mock_transport(monkeypatch, fail)
    result = run_endpoint()
    assert result["errors"] == 1
    assert "details" not in result["results"][0]["error"]


def test_recorded_and_fixture_modes_make_no_network_requests(monkeypatch):
    def unexpected_network(*args, **kwargs):
        pytest.fail("Recorded and fixture evaluation must not use the network")
    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    monkeypatch.setattr(rag_eval.httpx, "Client", unexpected_network)
    for config, expected_mode in [(RagEvalRequest(mock_responses={"q": "a"}), "recorded"),
                                  (RagEvalRequest(demo_mode=True), "fixture")]:
        result = rag_eval.RagEvaluationAgent().run({
            "cases": [{"question": "q", "candidate_reference_answer": "a"}], "config": config,
        })
        assert result["errors"] == 0
        assert result["total_cases_evaluated"] == 1
        assert result["evaluation_mode"] == expected_mode
        assert result["avg_reference_token_recall"] == 1.0
