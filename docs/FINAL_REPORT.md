# RAGTrust | Final implementation and demonstration report

Historical document notice — this report preserves the September 26, 2026 submission snapshot, including the earlier private hosted Foundry workflow. The October 8 public launch configuration supersedes its private-password and live-host instructions: the public demo uses anonymous temporary sessions and deterministic fixtures with Foundry disabled. Public launch verification is pending. Use [the current README](../README.md), [public demo guide](PUBLIC_DEMO.md), and [deployment manifest](DEPLOYMENT_MANIFEST.md) for current configuration; the measurements below remain historical evidence.

Prepared for Sai Nithin Krishna | Microsoft Agent-a-thon Architect | 25 September 2026

## 1. What the project does

RAGTrust expands a small trusted question-and-answer dataset into new evaluation cases, independently checks the generated answers against source evidence, records quality assessments, and exports a reusable dataset. The intended users are RAG developers, evaluation engineers, QA teams, and domain experts.

The main output is an evaluated dataset. Connecting a separate RAG application is optional. The sample security policy is demonstration input; the product is not a security-monitoring or factory-diagnosis application. A different domain can be evaluated by creating a new project and uploading its own golden examples and documents.

The implemented release is a working text-first demonstration product. It includes four named Microsoft Foundry prompt agents, a Streamlit interface, a FastAPI service, a Python orchestrator, persisted records, review controls, and versioned exports. The larger blueprint also describes raw-media processing, distributed workers, managed storage, and stronger evaluation research. Those items are explicitly separated from the implemented demo in Section 8.

The public application address is https://ragtrust-sainithin-public-2026.azurewebsites.net/. A private demo password protects the workspace. The password is kept in the local .private folder and must not be included in a public repository, document, recording, or submission archive.

## 2. Architecture and responsibility boundaries

The browser presents the eight-stage Streamlit workspace. The UI calls the orchestration service directly in the web process. FastAPI exposes an alternative programmatic interface to the same service; it is packaged and locally tested but is not a second publicly hosted API in this deployment.

The orchestrator owns the sequence, state changes, candidate cap, repair limit, cancellation flag, database writes, and exports. Four Foundry prompt agents perform bounded language-model tasks. Python performs schema validation, citation existence checks, duplicate detection, aggregation, hashes, and release creation.

The current web app runs on an Azure App Service F1 Free Linux plan in Canada Central. Model inference runs in the existing ragtrust-foundry-sweden resource and ragtrust-architect project, using the gpt-4o deployment. The web app has a system-assigned managed identity with Cognitive Services User access scoped to that Foundry account. The deployment uses HTTPS and App Service environment settings. No additional model deployment was created.

SQLite stores projects, golden examples, source assets, evidence segments, generation runs, candidate attempts, metric assessments, review decisions, dataset versions, quality reports, and optional RAG runs. The cloud working directory is /home/data. Source files and release files remain associated with project IDs. This is a single-owner demo workspace with a shared access password, not a multi-tenant identity or authorization system.

Application Insights is configured for operational tracing. Prompt-content capture is disabled. A configured telemetry client does not prove that every trace arrived or that all Azure costs have been measured; those claims require separate portal evidence.

## 3. How the four agents work

### Dataset Understanding and Planning

Foundry asset: ragtrust-dataset-understanding, version 2. Its input contains trusted seed examples, source evidence snippets, the domain, and requested configuration. It identifies topics, describes gaps and conflicts, and proposes topic quotas. Code validates the plan, enforces nonnegative quotas that sum to the target, and preserves the user's configured difficulty mix, question types, and language.

Golden examples guide domain and answer style. They do not establish every possible fact in that domain. Calibration and held-out records are excluded from generation seeds. If the user supplies only golden examples, RAGTrust constructs a restricted evidence boundary from their trusted answers. This supports controlled variants of existing facts rather than inventing new knowledge.

### Generation

Foundry asset: ragtrust-generation, version 2. The generator receives the plan, seed records, and source evidence. It returns a structured list of questions, provisional answers, expected behavior, topic, difficulty, scenario, modality, seed IDs, source references, and required facts. Supported scenarios include direct questions, paraphrases, comparisons, multi-step questions, and unanswerable cases.

Pydantic checks the returned structure. The application caps the number of candidates even if the model returns more. It normalizes recognized segment IDs into exact evidence locators and derives source lineage from the cited evidence. Unknown seed IDs are discarded. References remain marked automatically_derived until a person reviews them. The generator cannot self-certify correctness.

### Independent Verification

Foundry asset: ragtrust-independent-verification, version 2. Each verification request receives the candidate question and answer, the original evidence, citation locators, expected behavior, and required-fact checklist. It does not receive the generator's confidence or persuasive rationale. The judge returns structured claim assessments, evidence support, completeness, relevance, answerability, and a proposed status.

Code then enforces the evidence contract. An answering case with missing evidence or an invalid locator cannot pass merely because the judge says accepted. Unsupported or contradictory claims prevent automatic acceptance. Scores outside their valid range or malformed output cause an explicit failure. An answer with no claim assessments is sent to review.

Independent here describes separate requests and responsibilities. The roles share the same model deployment, so common model errors remain possible. Judge reliability must be checked against independently labelled examples before making claims about real-world correctness.

### Coverage and Refinement

Foundry asset: ragtrust-coverage-refinement, version 2. The repair role receives failed claims and evidence. It removes unsupported content or replaces it with supported facts. The application creates a new linked attempt and sends it back through verification. Earlier attempts remain available for inspection. Once the repair limit is exhausted, unresolved cases move to review.

## 4. End-to-end user workflow

1. Open the application and enter the private demo password before recording. Create a project with a name, domain, and purpose, or load the supplied IT-security sample.

2. Import golden CSV or JSONL examples. Map the question, trusted-answer, topic, evidence, and ID fields where the interface offers mapping controls. Supporting sources can be text, text-extractable PDF, or supported timestamped transcript files. The extractor preserves locators and file hashes. A scanned PDF without extractable text is marked needs_ocr rather than treated as usable evidence.

3. Inspect the profile and planning page. Review topic quotas, evidence gaps, and conflicts. The generation page accepts explicit quotas as JSON. The quotas must sum to the requested candidate count.

4. Set a small live demo run: candidate target 2, accepted target 1, repair limit 1, English, and 20 candidate budget units. Budget units restrict candidate volume using a simple application rule; they are not token accounting or a currency estimate.

5. Start generation. The UI enqueues work in a background thread and persists the run record. Refresh progress to see queued, running, completed, shortfall, cancelled, or failed status. Cancellation is checked between candidates; an already-running provider call finishes first.

6. Inspect each candidate's question, answer, references, recorded scores, and failed checks. Approve, reject, or correct the latest attempt. A human correction changes the reference origin and invalidates old automated scores because they described a different answer. A reviewed record is not automatically a representative audit of the dataset.

7. Open Dataset Quality to inspect the accepted-case topic coverage, duplicate analysis, distribution distance, and faithfulness average. Keep the population clear: generated rows and accepted rows answer different questions.

8. Release a completed run. The release contains dataset.jsonl, dataset.csv, case_assessments.jsonl, quality_report.html, and summary.json. The interface offers downloads for all five outputs. A subsequent release creates a new version; the earlier files remain unchanged.

9. Optionally test an external RAG endpoint or import recorded question-to-answer responses. Only the question is sent to the target; reference answers remain separate. The adapter evaluates the frozen release rather than mutable case rows. Fixture responses require an explicit demo selection and are visibly labelled.

## 5. Evaluation and interpretation

Faithfulness is an automated estimate of how many factual claims are supported by the supplied evidence. The average is calculated over assessed accepted cases, with an evaluated count. It is not external truth or a human-audited correctness percentage.

Factual F1 is marked not assessed when there is no independently trusted answer to the exact generated question. A nearby golden answer or the generator's own answer is not a valid substitute. Completeness uses a question-specific checklist, but a generated checklist itself remains provisional.

Citation checking has two parts: code confirms that the locator exists, while the judge assesses whether the cited text supports the claim. Exact duplicates are normalized repeated questions; later duplicates are rejected. The current near-duplicate detector uses character-trigram cosine similarity with a threshold of 0.82. It is a lexical heuristic, not a calibrated semantic embedding metric.

Topic coverage is measured against positive configured quotas for accepted final attempts. Distribution alignment uses Jensen-Shannon distance between target and observed topic distributions. Reports include counts before and after filtering and breakdowns by topic, difficulty, scenario, and modality.

The evaluator calibration tool reports agreement, defect precision, recall, F1, a confusion matrix, and Cohen's kappa against supplied labels. The included small benchmark is a demonstration fixture, not a representative independent audit. Human correctness therefore remains not assessed until a suitable audit is performed.

The optional RAG adapter records answers, latency, failures, reference-token recall, and heuristic abstention matching. Word overlap is not reported as faithfulness or factual accuracy. Semantic answer quality and retrieval quality remain not assessed without their required evidence and evaluators. HTTP errors and missing recordings are separate errors, not low-quality answer scores.

## 6. What was verified

The final code passed 35 automated tests before packaging. The suite covers the API lifecycle, generation and release, wrong numbers, unsupported claims, incomplete answers, invalid citations, duplicates, valid abstention, timestamp validation, bounded repairs, linked history, frozen releases, held-out seed separation, failed-run persistence, access protection, and safe report rendering.

A real version 2 Foundry run completed through the locally running application service. Run ID: f1a2ff2f-cde8-45d0-8e26-186af813b0bc. Dataset version ID: d4957234-bbda-4a2a-81b9-f4640dccf444. It generated 2 cases, accepted 2, rejected 0, required 0 repairs, and had no target shortfall. Its two planned topics met their quotas. The measured accepted-case faithfulness average was 1.0, exact duplicate rate 0, and lexical near-duplicate count 0. The release records Foundry version 2 explicitly alongside the internal prompt-pack label.

This two-case result is a connectivity and workflow demonstration. It is too small to establish general quality, a population accuracy claim, or a production reliability guarantee. The sample evidence and case assessments are included separately so a reviewer can inspect what was measured.

The four version 1 prompt agents were individually invoked previously, including a repair from a wrong monthly access-review claim to the supported quarterly claim. Version 2 adds instructions to treat document content as data, and the end-to-end run verifies the active planner, generator, and verifier integration. The final deployment receipt records the current cloud validation separately.

## 7. Improvements made during the final review

The final review replaced the hard-coded run configuration with real UI controls and background execution, scoped case and quality pages to the active project, enforced typed output boundaries, and made deterministic citation failures override model acceptance. Structured failed-claim explanations are preserved as text before validation, never discarded or converted into passing results.

Repair attempts now loop up to the configured limit and retain linked history. Failed provider execution is persisted as a failed run. Held-out and calibration examples are excluded from generation. A golden-only run stays within seed facts. Releases reject unfinished runs, preserve a frozen dataset for later RAG testing, and update exported counts after review.

Reports now escape source/model text, state metric definitions and populations, include source and configuration data, and avoid invented universal quality targets. Unavailable factual correctness is explicitly unassessed. The optional RAG adapter no longer silently synthesizes target answers or displays a fixed relevance score.

The cloud workspace has a private access gate and a version pin for Foundry prompt agents. The deployment script builds from an explicit file allowlist and stores the demo password only in a local ignored directory and Azure app settings. The source package excludes credentials, virtual environments, runtime databases, caches, and uploaded private files.

## 8. Blueprint alignment and remaining work

Implemented: the core text dataset-generation, validation, review, reporting, and export workflow; four persisted Foundry prompt agents; source references and hashes; project-scoped data views; bounded repairs; failure persistence; optional recorded/live response capture; local API; hosted Streamlit demo; and a reproducible source/container package.

Partially implemented: multimodal support accepts timestamped transcripts but does not inspect original images, audio, video frames, or motion. PDF OCR requirements are detected but OCR is not performed. Lexical near-duplicate detection is implemented, while calibrated semantic duplication and systematic comparisons with seed families need additional work. Coverage gaps are reported but are not automatically filled by repeated generation batches.

Still a roadmap item: distributed, restart-resumable jobs; managed PostgreSQL and Blob Storage adapters; per-user identity and tenant authorization; a calibrated Ragas metric adapter; representative human audits and confidence intervals; exact provider token/cost accounting; retrieval precision/recall metrics; and asynchronous continuous live-traffic evaluation.

The current worker records progress in the database but runs inside one web process. A process recycle can interrupt a run. For the recording, use a small run and export the result after it completes. The F1 host can cold-start or exhaust its free compute quota, so retain the locally runnable version and sample release as the fallback demonstration.

These boundaries should be stated in the presentation. The project is ready to demonstrate its implemented text-first workflow; it should not be described as completing every enterprise and raw-media feature in the larger blueprint.

## 9. Integration and extension techniques

The system uses explicit adapters and typed contracts, not a general plugin marketplace or autonomous tool discovery. The Foundry adapter is in src/ragtrust/agents/foundry_client.py. It sends a bounded task payload through the Responses API with an agent_reference containing the named asset and configured version. Definitions live in foundry_definitions.py. A prompt update creates a new Foundry version; the application version pin is changed only after verification.

Agent implementations expose a run method with structured inputs and outputs. The planner returns a coverage plan; generation returns CandidatePayload records; verification returns VerificationOutput. To add a new agent role, define the input/output contract, add an adapter, connect it at an explicit point in OrchestrationService, and test malformed output, missing evidence, failure, cancellation, and quota behavior. A role should not receive broader data or cloud permissions simply because it is an agent.

Source ingestion is an extraction boundary. A future OCR, image, audio, or video adapter must return evidence segments with stable locators, source-version lineage, modality, and timestamp or region information. It must expose extraction failures instead of inventing evidence. The current extractor supports text and supported transcripts; a JSON filename alone does not establish video understanding.

Metric integrations must define a scale, applicability, evidence inputs, evaluator version, and the population being summarized. Missing inputs must produce not_assessed rather than a default passing score. Ragas is an optional future adapter: installing its package does not mean its metrics are used. Any new metric requires independently labelled calibration examples and tests before being presented as a quality guarantee.

The optional RAG target adapter accepts a public HTTPS endpoint. It posts a JSON object with a query field, and accepts an answer or response string. It blocks local/private destinations and redirects, separates HTTP failures from answer quality, and retains the frozen reference dataset. Custom authentication or a different endpoint schema requires an explicit adapter change with secrets provided through private runtime settings.

LocalStorage and the SQLAlchemy models form the persistence boundary. Production Blob Storage, a managed database, durable job queues, and user authorization are planned integration points, not enabled implementations. Validate permissions, migrations, recovery, and tenant separation before replacing these components. The current shared password is only a demonstration access gate.

## 10. Run, deploy, and reproduce

From the ragtrust directory, create a Python 3.11 or newer virtual environment, install the pinned project dependencies, copy .env.example to .env, and fill only the required local settings. Fixture mode works without cloud credentials. Live mode needs the existing Foundry project endpoint, model name, versioned agents, and an authorized Azure identity.

Installation: python3 -m venv .venv ; then .venv/bin/pip install -e '.[dev]'. Run tests with .venv/bin/pytest -q. Start the UI with PYTHONPATH=src .venv/bin/streamlit run src/ragtrust/app.py. Start the API with PYTHONPATH=src .venv/bin/uvicorn ragtrust.api:app --host 127.0.0.1 --port 8000.

Live local authentication uses az login. Set FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL_NAME=gpt-4o, FOUNDRY_USE_DEPLOYED_AGENTS=true, FOUNDRY_AGENT_VERSION=2, and RAGTRUST_MODE=foundry. The deployment script updates an existing web app and does not create a new paid hosting plan. Use scripts/deploy_foundry_agents.py only when deliberately creating a new agent version.

Dockerfile and docker-compose.yml package UI and API services. The Docker image was not executed locally because the Docker daemon was unavailable. The Azure source package was built and tested separately. Container users should configure credentials through runtime settings and mount a persistent data volume.

Official integration references: Microsoft Foundry prompt-agent quickstart at https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/prompt-agent and runtime components at https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/runtime-components. The project uses the documented Responses API agent_reference contract to invoke named agent versions.

## 11. What to upload and how to record

Prepare the submission in the course final activity where you registered. The exact field limits, file-size limits, deadline, and video-length requirements must be checked in that form. The following is the project package, not a claim that the form has been submitted.

Upload the final PDF report as the supporting architecture and implementation document. Upload the submission bundle if ZIP attachments are accepted. If the form asks for a repository URL, publish the clean source ZIP contents to your own GitHub repository and paste that repository URL. Include the public application URL, and share the demo password privately with the reviewers only if they need workspace access.

Include the sample release evidence ZIP or its HTML report when supporting evaluation results are requested. It contains the actual live demo's JSONL, CSV, assessments, HTML, and summary. Do not present the sample's two accepted cases as a broad accuracy benchmark.

Record your own narrated video using docs/VIDEO_SCRIPT.md. A practical suggested duration is 5-7 minutes unless the course specifies otherwise. Sign in before recording; hide all passwords, tokens, environment settings, and private source documents. Show the problem, four Foundry agents, one small live run, one case's evidence and assessment, dataset quality, and the release downloads. End with the implemented scope and future work.

The final submission still requires your recorded video and your action in the course upload form. No video was recorded, no GitHub repository was published, and no course submission was sent by this implementation work.
