# Try the RAGTrust public demo

Launched and verified October 8, 2026. Open the demo without a password, or explore the public MIT-licensed repository and its issue tracker.

- [Open the demo](https://ragtrust-sainithin-public-2026.azurewebsites.net/)
- [Browse the source](https://github.com/Nithin9Krishna/ragtrust)
- [Report an issue](https://github.com/Nithin9Krishna/ragtrust/issues)

The public workspace demonstrates the evaluation workflow with deterministic fixtures. Microsoft Foundry calls are disabled for the public workspace, including at the client boundary. The source includes a separate, optional Foundry mode for your own local/private deployment. The hosted service exposes Streamlit, without a separately hosted public API.

Each browser session gets a separate temporary workspace and database. Sessions have a two-hour limit and reset on your next interaction after expiry. A disconnected session has a 120-second reconnect window. Download any exports you want to keep before leaving.

Use only public or non-confidential demonstration data. Do not upload customer records, internal documents, credentials, or private production responses. This is a demonstration service with no accounts or durable storage. Public limits are 20 candidates per run, one repair per case, and 5 MB per upload. The existing Azure F1 free host may take time to start or become temporarily unavailable.

## Walk through the sample

1. Open the demo and select **Load IT Security Demo Data** in the sidebar.
2. In **Profile & Plan**, keep a small candidate target and run the planning agent. Inspect the topic quotas and evidence gaps.
3. In **Run & Monitor**, start generation and verification, then refresh the progress. The generated cases use fixture templates; they are useful for exercising the application, not for demonstrating general-purpose AI synthesis.
4. In **Case Inspector**, read the question, proposed reference answer, cited evidence, and assessments. Review uncertain cases before approving them. In **Dataset Quality**, inspect coverage, duplicate checks, and the stated limitations.
5. In **Export & Release**, freeze an approved dataset version. Download the JSONL or CSV dataset, case assessments, and report.
6. Open **RAG Target Test** to compare responses from your own system using one of the options below. Dataset checks and target-response comparisons are separate reports.

You can also create a project and import your own small demonstration set. Golden examples support CSV or JSONL. Source evidence supports text, text-extractable PDF, and supported timestamped transcript files. A scanned PDF is marked as requiring OCR; the demo does not perform OCR, image understanding, or raw audio/video processing. Fixture templates may fit the supplied security example better than an arbitrary domain.

## Compare recorded responses

Recorded responses are useful when your RAG service is local, private, or uses an authentication contract this adapter does not support. Run the released questions through your RAG independently, then paste a JSON object into **Or recorded responses as a JSON question-to-answer mapping**:

```json
{
  "Exact question from the released dataset": "Answer returned by your RAG system"
}
```

Use the exact released question as each key and a string answer as its value. Leave the endpoint URL empty and the fixture-response checkbox unchecked. Missing answers are reported as errors. Recorded-mode latency measures the local comparison step, not your system's original response time.

## Connect a public HTTPS endpoint

Enter an endpoint you control in **RAG Endpoint URL**. It must be reachable on public HTTPS on port 443 and accept a JSON POST body:

```json
{"query": "The released evaluation question"}
```

It must return JSON containing either a string `answer` or a string `response`:

```json
{"answer": "Your RAG system's answer"}
```

The adapter sends the evaluation question. It does not send the reference answer or source documents. It currently has no API-key or custom-header configuration; use recorded responses if your endpoint requires authentication. Private, loopback, and local-network endpoints are rejected. The adapter connects to a validated public IP while preserving the endpoint's original Host and TLS server name. Proxies and redirects are disabled, and response bodies are limited to 1 MiB. Network failures, oversized or invalid responses, and timeouts appear as failed responses in the report.

## Read the results correctly

- **Reference token recall** measures overlap with words in the reference answer. A fluent wrong answer can overlap, and a correct paraphrase can score poorly.
- **Abstention phrase match** checks a small set of phrases when the expected behavior is abstention. It is a heuristic.
- **Latency and errors** describe the captured endpoint requests. Recorded and fixture modes do not benchmark your RAG's serving latency.
- **Semantic answer quality, factual accuracy, faithfulness, and retrieval quality** are not established by this adapter. Human correctness and evaluator reliability remain unassessed until representative human labels are supplied.

The **Use clearly labelled fixture responses** option copies reference answers solely to demonstrate the comparison screen. It is not a test of an external RAG system.

## Launch verification

The anonymous browser walkthrough loaded the supplied sample, generated four fixture cases with two accepted, froze version 1, and downloaded a two-row JSONL dataset. A second browser tab opened with no projects. A recorded-response smoke test evaluated two clearly synthetic answers with zero errors and the fixture-response checkbox unchecked.

These checks demonstrate the hosted workflow and session separation. They do not benchmark a real RAG system or prove answer accuracy. Endpoint transport controls passed automated tests; no cloud-hosted live endpoint test is claimed. See [the deployment manifest](DEPLOYMENT_MANIFEST.md) for exact evidence and [the passing CI run](https://github.com/Nithin9Krishna/ragtrust/actions/runs/37858292405) for Python 3.11/3.13 checks.

For broader evaluation or private data, run the source locally and configure the optional live integration in your own environment. See [the README](../README.md) for installation and supported deployment modes.
