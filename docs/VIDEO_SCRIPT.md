# RAGTrust recording walkthrough and narration

Historical document notice — this script preserves the September 26, 2026 submission snapshot. Its sign-in, hosted Foundry run, and 35-test narration describe that earlier private workflow. They are superseded for the October 8 public launch configuration, which uses anonymous temporary sessions and deterministic fixtures with Foundry disabled. Public launch verification is pending. Follow [the public demo guide](PUBLIC_DEMO.md) for a current public walkthrough; do not narrate these historical live-run instructions over public fixture output.

Suggested length: 5-7 minutes, unless the submission form sets a different limit. These are your speaking notes, not a claim that a video has already been recorded. Sign in before recording. Hide credentials and private files.

## 0:00-0:40 - The actual idea

Show the RAGTrust application.

“My project is RAGTrust. The product creates synthetic evaluation datasets for RAG applications. A team may have a small collection of trusted questions and answers, but needs more test coverage. Simply generating hundreds of questions is not enough: the new answers can be unsupported, duplicated, or unevenly distributed. RAGTrust combines generation with separate evidence-based verification and makes the result inspectable. The main deliverable is the dataset itself. Connecting a target chatbot is optional.”

## 0:40-1:20 - Trusted input and evidence

Open the IT Security sample project. Show the golden examples and policy source. Explain that security is just the demo domain.

“Golden examples teach the intended topics and answer style. Source documents provide the evidence boundary. RAGTrust extracts segments with locators and stores source hashes. An answer should be grounded in those segments, not just sound plausible. Calibration and held-out examples are excluded from generation seeds. Text and text-extractable PDFs work; timestamped transcripts have a narrow supported path. A scanned PDF is marked as needing OCR. This version does not understand raw images, audio, or video.”

## 1:20-2:30 - Architecture and four roles

Show the final report's architecture diagram, then the four version-2 assets in Foundry if available.

“The web interface runs on Azure App Service. A Python orchestrator coordinates four named Microsoft Foundry prompt agents using the existing GPT-4o deployment. These are versioned prompt assets, not four always-running containers. The application owns sequencing, data storage, validation, and exports.

“The first role understands the dataset and proposes a coverage plan. Code checks that topic quotas match the requested count. The second role generates provisional questions and answers with evidence references. Provisional means they are not trusted yet.

“The third role receives the candidate and original evidence, without the generator's confidence or rationale. It breaks the answer into claims and checks their support. Deterministic code still overrides an acceptance if the cited evidence is missing or invalid. Independence means separate requests and responsibilities; the roles use the same model and can share errors.

“The fourth role repairs fixable cases using failed claims and evidence. Each repair creates a linked attempt and is verified again. Unresolved cases go to review after the configured limit. Coverage gaps are reported, but automatic repeated generation to fill every gap is future work.”

## 2:30-3:35 - Run and inspect a case

Choose Microsoft Foundry mode. On Run & Monitor set candidate target 2, accepted target 1, repair limit 1, and the smallest valid budget covering two candidates. Leave quotas empty for the planner or supply a valid two-case quota. Start once and use Refresh progress. Do not repeatedly start runs if a provider call is slow.

“This is a small live run to stay within the available quota. The interface records progress and reports failures or target shortfalls explicitly. It never turns a failed live request into a fake fixture success. The offline fixture mode is separately labelled.

“Here is a case: its question, candidate reference answer, source locator, and verification result. The question is accepted only through the workflow; that is not a human accuracy guarantee. Unsupported claims are repaired, rejected, or reviewed. The complete attempt history remains available.”

If live execution is delayed, disclose it and show the included completed live sample instead. Do not present fixture output as live output.

## 3:35-4:35 - Quality, review, release

Show Dataset Quality and Case Inspector, then Export & Release.

“Dataset quality reports accepted-case topic coverage, exact duplicates, lexical near-duplicate candidates, and distribution distance. The near-duplicate metric is a character-trigram heuristic, not a semantic embedding benchmark. Faithfulness is an automated claim-support estimate. Factual F1 is not assessed when there is no independently trusted answer to the exact generated question. Human correctness also remains unassessed without a representative audit.

“A reviewer can approve, reject, or correct the latest attempt. Correcting an answer invalidates the old automated scores. Releasing a completed run produces five files: canonical JSONL, flattened CSV, case assessments, an HTML quality report, and a JSON summary. A new release creates a new version without changing the earlier files.”

## 4:35-5:05 - Optional downstream RAG test

Open the RAG Target Test stage. Do not claim a real target was tested if none is connected.

“After release, I can test a separate public HTTPS RAG endpoint or import recorded responses. The target receives the question, not the reference answer. This adapter reports latency, failures, reference-token recall, and heuristic abstention matching. It does not claim semantic faithfulness, factual accuracy, or retrieval precision from word overlap. Dataset quality and target-system performance remain separate.”

## 5:05-6:00 - Evidence and honest conclusion

Show the measured sample quality report and final report.

“Thirty-five automated tests passed, covering the API lifecycle, citations, unsupported claims, repair history, failed runs, held-out separation, release behavior, access protection, and safe reporting. The included version-2 live sample generated two cases and accepted both, met its two topic quotas, and recorded no duplicates. This proves the demonstrated connectivity and workflow; two cases do not establish general accuracy.

“The current release is a working text-first demonstration. The free Azure host can cold-start, and its worker is not restart-resumable. Production scaling, per-user identity, raw-media processing, semantic metric calibration, exact cost accounting, and representative human audits remain future work. RAGTrust's value is a traceable route from small trusted examples to an inspected, reusable evaluation dataset.”

End on the app URL and the final report. Add your own repository and video links only after publishing them. Course submission is a separate final step.
