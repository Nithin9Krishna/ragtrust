# RAGTrust User Manual

**Public demo · Version 0.1 · October 8, 2026**

[Download the illustrated nine-page PDF](RAGTrust_User_Manual.pdf) to keep or attach when sharing RAGTrust.

[Open RAGTrust](https://ragtrust-sainithin-public-2026.azurewebsites.net/) · [Public repository](https://github.com/Nithin9Krishna/ragtrust) · [Report an issue](https://github.com/Nithin9Krishna/ragtrust/issues)

RAGTrust helps you build, inspect, release, and use an evaluation dataset for a retrieval-augmented generation (RAG) system. The hosted public demo requires only a browser.

The public demo generates and verifies cases with deterministic fixtures, without Microsoft Foundry inference. These templates fit the supplied IT security sample better than an arbitrary domain. You can compare your RAG's answers, but lexical comparison does not establish factual accuracy, semantic quality, or retrieval quality.

## 1. First visit: a quick walkthrough

1. Open the demo. If the free host is slow to start, allow it time to load.
2. In the sidebar, click **Load IT Security Demo Data**. This creates a sample project with golden examples and source evidence.
3. Open **2. Profile & Plan**. Keep **Candidate Target** at 4, **Accepted Target** at 2, **Max Repairs per Case** at 1, and **Candidate budget units** at 20. Click **Run Planning Agent**; inspect topic quotas and any evidence gaps or conflicts.
4. Open **3. Run & Monitor**. Check its separate configuration: candidate target 4, accepted target 2, repair limit 1, and budget 20. Click **Start Generation & Verification Run**, then **Refresh run progress** until the run completes.
5. Open **4. Case Inspector**. Read questions, candidate reference answers, evidence references, assessment reasons, and failed checks. Review uncertain cases using the instructions below.
6. Open **5. Dataset Quality**. Check topic coverage, duplicates, distribution distance, and disclosures. A shortfall is information to investigate, not a guarantee that every target will be met.
7. Open **7. Export & Release**. Choose the completed run and click **🔒 Freeze & Release Dataset Version**. Download your dataset and reports before leaving.
8. Open **8. RAG Target Test** to compare your own recorded answers or a compatible public endpoint. Keep fixture responses unchecked when testing your system.

## 2. Find your way around

| Tab | Use it to |
|---|---|
| **1. Project & Ingest** | Create a project; import trusted examples and source evidence. |
| **2. Profile & Plan** | Propose topic quotas and identify evidence gaps or conflicts. |
| **3. Run & Monitor** | Configure and start generation; inspect progress and shortfalls. |
| **4. Case Inspector** | Inspect individual cases; approve, reject, or correct answers. |
| **5. Dataset Quality** | Review coverage, duplicates, and accepted-case assessments. |
| **6. Validate Evaluator** | Run the supplied calibration example and inspect its confusion matrix. |
| **7. Export & Release** | Freeze a version and download datasets and reports. |
| **8. RAG Target Test** | Capture and compare answers for a released version. |

Select your project in the sidebar.

## 3. Use your own demonstration data

In **1. Project & Ingest**, enter **Project Name**, **Domain**, and **Purpose & Evaluation Goals**, then click **Create Project**. Select it before importing public or non-confidential samples.

For **Upload Golden Examples (CSV / JSONL)**, the required column names or JSON keys are `question` and `answer`. Both must contain non-empty strings; rows missing either are skipped. Optional fields are `id`, `topic`, and `evidence_ref`. Topics default to `general`; identifiers are generated when omitted. Use UTF-8 and lowercase file extensions.

Example `golden.csv`:

```csv
id,question,answer,topic,evidence_ref
seed-1,"When must a suspected incident be reported?","Within 60 minutes of detection.",Incident Reporting,policy.txt:sec1
```

The equivalent `golden.jsonl` contains one JSON object per line:

```json
{"id":"seed-1","question":"When must a suspected incident be reported?","answer":"Within 60 minutes of detection.","topic":"Incident Reporting","evidence_ref":"policy.txt:sec1"}
```

The importer also accepts a `.json` array. Verify the **Parsed** count, then click **Import Golden Examples**. Input `answer` becomes the trusted seed answer; releases use `candidate_reference_answer` for generated or reviewed references.

Use **Upload Source Material (TXT / PDF / Video JSON)** for `.txt`, `.pdf`, `.json`, or `.vtt` files. Check the extracted evidence count, then click **Register Source Material**. Separate TXT paragraphs with blank lines: the first paragraph of `policy.txt` receives the locator `policy.txt:sec1`. Match any supplied `evidence_ref` to the appropriate source locator.

PDFs must contain extractable text. A scanned PDF with no extractable text is registered as requiring OCR; the demo does not perform OCR or invent its contents. Transcript JSON uses a `segments` or `transcript` array with `start`, `end`, and `text`; times are seconds and `end` must exceed `start`. An optional `speaker` identifies the speaker. VTT and timestamped `.transcript.txt` files provide transcript text, not raw video or audio understanding.

## 4. Plan, generate, and review

The candidate target sets the number of proposed cases; the accepted target sets the desired usable count and cannot exceed the candidate target. Public runs allow up to 20 candidates and one repair per case. Budget units are workflow limits, not currency: generation allows two units per candidate. A small budget can reduce the generated count.

Planning and run configuration are separate screens. Review the plan, then enter the intended values in **3. Run & Monitor**. Optional approved topic quotas must be a JSON object with non-negative counts totaling the candidate target, for example `{"Incident Reporting":2,"Access Control & MFA":2}` for four candidates.

Run statuses include `queued`, `running`, `completed`, `completed_shortfall`, `cancelled`, and `failed`. **Cancel active run** requests cancellation. Refresh to inspect the outcome. `completed_shortfall` means the run finished below its accepted target; read **Auditor Disclosures & Notes** before releasing it.

Case statuses include `accepted`, `needs_revision`, `needs_review`, and `rejected`; a case may also be `generated` or `checking` during processing. An automated accepted status is not a representative human correctness audit.

In **4. Case Inspector**, use **Filter Status** or **Filter Modality**. Review the latest attempt if a case has been repaired. Compare the answer with your original source and its cited locator:

- **✅ Approve** records your approval and accepts the case.
- **❌ Reject** excludes the case from accepted releases.
- Enter a non-empty **Correct Answer** and click **Submit Correction** to replace the answer and approve it. Previous scores become **Not assessed** because they describe the earlier text.

Review before freezing a version to share.

## 5. Release and keep your results

**7. Export & Release** accepts runs marked `completed` or `completed_shortfall`. A release snapshots accepted cases; later case edits do not rewrite its files. Freeze another version after corrections when you need updated exports.

Available downloads are **📥 Download JSONL**, **📊 Download CSV**, **📄 Download Quality Report (HTML)**, **Download all case assessments** (JSONL), and **Download machine-readable summary** (JSON). The assessment download includes cases and repair attempts beyond the accepted dataset. SHA256 values identify the dataset files. A frozen release remains temporary in the hosted session; downloading it is how you retain a copy.

## 6. Compare your RAG's answers

First select **Select Approved Dataset Version** in **8. RAG Target Test**.

**Recorded answers:** Download the released questions and run them through your own RAG independently. Paste a JSON object in **Or recorded responses as a JSON question-to-answer mapping**, or use **Upload recorded responses (JSON question-to-answer mapping)**:

```json
{"Exact question copied from the released dataset":"Answer returned by your RAG"}
```

Each key must exactly match a released question; each value must be a string. Supply all questions to avoid missing-answer errors. An uploaded file takes precedence over the text area. Leave **RAG Endpoint URL (Optional)** empty, leave **Use clearly labelled fixture responses (demonstration only)** unchecked, and click **Run RAG Endpoint Evaluation**.

**Public endpoint:** Enter an endpoint you control that accepts a JSON POST body `{"query":"The released question"}` and returns `{"answer":"Your answer"}` or `{"response":"Your answer"}`. The answer must be a string. Only the question is sent, without the reference answer or source documents.

The endpoint must use public HTTPS on port 443. Authentication headers and API keys are not configurable. Private, loopback, and local-network destinations, proxies, and redirects are unsupported. Responses must be uncompressed JSON, no larger than 1 MiB, and meet the 15-second response limit. Use recorded answers for local, private, or authenticated systems. Inspect failed responses in the results table.

The fixture checkbox copies reference answers to demonstrate the screen; it does not test an external RAG.

## 7. Interpret results carefully

**Reference token recall** measures word overlap with the reference. Incorrect answers may overlap, while correct paraphrases may score poorly. **Abstention phrase match** checks a small phrase list when abstention is expected. **Semantic quality** remains **Not assessed**. The adapter does not establish answer correctness, faithfulness, or retrieval performance.

**Avg Latency** describes captured requests in endpoint mode. Recorded and fixture modes time local comparison work, not your RAG's original response time. Check evaluation mode and failed-response count before interpreting averages.

Dataset coverage compares topic targets with accepted cases; duplicate checks detect exact or lexical similarity. Distribution distance describes differences in topic balance. Fixture claim-support scores and the supplied **Run Evaluator Calibration Benchmark** demonstrate checks on a small supplied example. Neither proves reliability on your domain; representative human labels are required.

## 8. Session limits and troubleshooting

Each browser session has a separate temporary workspace. It expires after two hours and resets on the next interaction; disconnected sessions have a 120-second reconnect window. **Reset my workspace** clears your current workspace. There are no accounts or durable storage. Download before leaving. Uploads are limited to 5 MB. Azure's free host may start slowly or become temporarily unavailable.

| Problem | What to try |
|---|---|
| Site loads slowly or is unavailable | Wait for the free host to start, then retry. |
| Golden import shows zero examples | Check `question` and `answer`, non-empty strings, CSV quoting, or valid JSON. |
| PDF has zero evidence segments | Apply OCR outside the demo or upload a text-extractable PDF/TXT. |
| Run rejects configuration or falls short | Check accepted ≤ candidate, quota totals, budget, evidence, and disclosures. |
| Target responses fail or scores surprise you | Check exact recorded keys or endpoint contract; inspect errors and lexical limitations. |

For reproducible issues, use the [issue tracker](https://github.com/Nithin9Krishna/ragtrust/issues) with public sample steps and the visible error. Avoid including confidential uploads or credentials.

## Glossary

**Golden example:** a trusted seed question and answer. **Evidence:** source text supporting an answer. **Candidate:** a proposed evaluation case. **Reference answer:** the answer used for comparison. **Fixture:** a deterministic demonstration template or rule. **Release:** a frozen dataset snapshot. **Abstention:** declining to answer when evidence is insufficient.
