# RAGTrust Demo Video Script

## 0:00–0:30 — Problem and promise

“RAG applications can sound confident even when their answers are unsupported. Teams need high-quality evaluation data, but building it manually is slow and difficult to audit. RAGTrust is a multi-agent system that generates synthetic RAG evaluation cases, verifies every claim independently, and publishes a traceable evaluation release.”

Show the RAGTrust home page and point to the workflow stages.

## 0:30–1:15 — Inputs and project setup

“A domain expert starts by creating a project. Golden examples teach the system the intended domain and answer style. Source documents provide the evidence boundary. RAGTrust hashes and stores each source, extracts addressable evidence segments, and refuses to treat a scanned PDF as evidence when OCR has not been performed.”

Create or open the security/compliance demo project. Show the golden CSV and policy source.

## 1:15–2:20 — Multi-agent architecture

“The first Foundry agent understands the dataset and produces topic quotas, difficulty mix, and gap disclosures. The second Foundry agent generates provisional questions and candidate answers grounded in exact evidence locators. The third agent is independent: it does not receive the generator’s confidence or rationale. It decomposes the answer into claims and verifies each claim against the original evidence. A fourth agent performs bounded repair when a case is fixable. If a repair limit is reached or confidence is insufficient, the case goes to human review.”

Show the architecture diagram and the four agents in Microsoft Foundry.

## 2:20–3:20 — Run and quality controls

“I choose the candidate target, accepted target, and repair limit, then start a live Foundry run. Models do semantic work, but deterministic Python controls the trust boundary. It validates citation existence, normalizes source IDs into immutable locators, detects exact and near duplicates, calculates topic coverage and distribution divergence, and records parent-child repair history.”

Start a small run. Show progress, cases, metrics, and a case-level explanation.

## 3:20–4:10 — Human review and immutable release

“Accepted, rejected, repairable, and uncertain cases remain visible. A reviewer can approve, reject, or correct a case. When the dataset is ready, RAGTrust creates an immutable version containing canonical JSONL, flattened CSV, case-level assessments, a human-readable HTML report, and a machine-readable summary. Hashes and provenance make the release auditable.”

Show review controls, then the generated release files and report.

## 4:10–4:45 — Optional target RAG evaluation

“Dataset quality and system quality are separate. After release, the same approved cases can optionally be sent to a target RAG endpoint. Its answers, latency, relevance, faithfulness estimate, and abstention behavior are reported separately, so a weak target system cannot contaminate the dataset-quality claim.”

Show the optional RAG testing section without claiming a production target if none is connected.

## 4:45–5:20 — Azure proof and conclusion

“The four role agents are persisted and versioned in the existing Microsoft Foundry project, use the deployed GPT-4o model, and emit traces to Application Insights when configured. In the verified live run, RAGTrust generated two cases, independently accepted both, achieved complete topic coverage, and found no duplicates. Twenty-six automated tests cover the API, orchestration, repair history, citations, duplicates, calibration, releases, and extraction.”

End on the public application URL, repository contents, and quality report.

## Claims to avoid in the video

- Do not say Ragas produced the current scores.
- Do not claim raw image, audio, or video understanding.
- Do not call automated scores human correctness.
- Do not claim the local SQLite/in-process-worker build is horizontally scalable.
- Do not display `.env`, connection strings, tokens, passwords, or subscription secrets.
