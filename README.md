# RAGTrust

RAGTrust is a working multi-agent application for creating, independently validating, reviewing, and exporting synthetic evaluation datasets for retrieval-augmented generation systems.

Public demo: https://ragtrust-sainithin-public-2026.azurewebsites.net/

The core product works without a connected RAG endpoint. Optional RAG endpoint testing is a separate workflow and report.

## What is implemented

- Streamlit interface for project creation, upload, planning, generation, monitoring, review, calibration, release, and optional RAG testing.
- FastAPI API for the same core lifecycle.
- Four application-orchestrated roles persisted as versioned Microsoft Foundry prompt agents:
  - Dataset Understanding and Planning Agent
  - Generation Agent
  - Independent Validation Agent
  - Coverage and Refinement Agent
- Microsoft Foundry model integration through `azure-ai-projects` 2.x and `DefaultAzureCredential`.
- Explicit fixture mode that is deterministic, offline, and labelled in reports. Live Foundry failures fail closed; they never silently become fixture results.
- SQLite persistence through SQLAlchemy with PostgreSQL-compatible models for projects, sources, evidence, golden examples, runs, cases, metrics, reviews, releases, reports, and optional RAG runs.
- Database-backed run state plus a local background worker endpoint, cancellation flag, bounded repair attempts, budget-limited candidate generation, and target-shortfall reporting.
- CSV and JSONL golden dataset import.
- Text and PDF extraction. PDFs without extractable text are marked `needs_ocr` and are not treated as evidence.
- Narrow video/transcript evidence support using JSON, VTT, or SRT-style timestamped segments. Invalid timestamp ranges are rejected.
- Original uploaded files saved in project-isolated local storage through a storage abstraction.
- Deterministic citation, structure, numeric support, exact-duplicate, semantic-near-duplicate, coverage, and Jensen-Shannon distribution checks.
- Independent claim-level fixture evaluator and optional live Foundry evaluator.
- Human-labelled evaluator calibration with accuracy, precision, recall, F1, confusion matrix, and Cohen's kappa.
- Immutable versioned releases containing:
  - canonical JSONL dataset
  - flattened CSV dataset
  - case-level JSONL assessments
  - HTML quality report
  - machine-readable JSON summary
- Optional RAG endpoint or recorded/mock-response testing kept separate from dataset quality.
- Application Insights/OpenTelemetry initialization when configured.

## Honest limitations

- Fixture mode uses documented deterministic rules. It is useful for testing the workflow but is not live model generation or independent proof of correctness.
- The current text evaluator is a transparent prototype rubric, not Ragas. `ragas==0.4.3` is provided as an optional dependency for a later calibrated metric adapter; Ragas is not used to produce the included demo scores.
- Human-audited correctness and judge reliability appear as `not assessed` until representative human labels are supplied.
- PDF OCR is detected but not performed automatically.
- The working multimodal path accepts timestamped transcript evidence. It does not perform audio transcription, video motion understanding, or visual-only verification. Transcript evidence must not be presented as proof of a visual claim.
- Uploaded images and raw audio/video extraction are not supported by this version. Do not claim universal format support.
- The local background worker is durable in the database but is not a distributed production queue. A production deployment should use a queue worker such as Azure Service Bus plus a worker service.
- The optional RAG adapter assumes an HTTP endpoint accepting `{"query": "..."}` and returning `answer` or `response`. Retrieval metrics are not computed unless retrieved IDs and relevance labels are added.

## Installation

From the `ragtrust` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
cp .env.example .env
```

The committed `.env.example` contains placeholders only. Never commit real connection strings or keys.

## Environment variables

Local fixture mode requires no cloud credentials:

```dotenv
RAGTRUST_MODE=fixture
RAGTRUST_DATA_DIR=./data
RAGTRUST_DATABASE_URL=sqlite:///./data/ragtrust.db
RAGTRUST_MAX_CANDIDATES=100
RAGTRUST_MAX_REPAIRS=2
```

Live Foundry mode uses the existing project and model deployment and does not provision resources:

```dotenv
RAGTRUST_MODE=foundry
FOUNDRY_PROJECT_ENDPOINT=https://RESOURCE.services.ai.azure.com/api/projects/PROJECT
FOUNDRY_MODEL_NAME=gpt-4o
FOUNDRY_USE_DEPLOYED_AGENTS=true
APPLICATIONINSIGHTS_CONNECTION_STRING=
AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false
```

Authenticate with Azure CLI before using Foundry mode:

```bash
az login
```

## Run the measured local demo

```bash
PYTHONPATH=src .venv/bin/python -m ragtrust.orchestrator
```

The command loads the clearly labelled IT-security fixture dataset, executes all four roles, validates and repairs cases, records the target shortfall if applicable, and writes a versioned release under `data/releases/`.

The included demo inputs are under `demo_data/`:

- `golden_support_qa.csv`
- `security_compliance_policy.txt`
- `security_walkthrough_video.json`
- `calibration_benchmark.json`

## Start the interface

```bash
PYTHONPATH=src .venv/bin/streamlit run src/ragtrust/app.py
```

Open the URL printed by Streamlit, normally `http://localhost:8501`.

## Start the API

```bash
PYTHONPATH=src .venv/bin/uvicorn ragtrust.api:app --host 127.0.0.1 --port 8000
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

Useful endpoints include:

- `POST /projects`
- `POST /projects/{id}/golden-examples`
- `POST /projects/{id}/sources`
- `POST /projects/{id}/profile`
- `POST /projects/{id}/generation-runs` for a synchronous run
- `POST /projects/{id}/generation-jobs` for a local background job
- `POST /generation-runs/{id}/cancel`
- `GET /generation-runs/{id}`
- `GET /generation-runs/{id}/cases`
- `POST /cases/{id}/review`
- `POST /generation-runs/{id}/releases`
- `GET /datasets/{id}/report`
- `GET /datasets/{id}/export?format=jsonl|csv|assessments`
- `POST /datasets/{id}/rag-runs`
- `POST /evaluator/calibrate`

## Run tests

```bash
.venv/bin/pytest -q
```

## Deploy and verify the Foundry agents

The deployment command creates a new immutable version of each named agent in the configured existing project. It does not create a Foundry resource, project, or model deployment.

```bash
PYTHONPATH=src .venv/bin/python scripts/deploy_foundry_agents.py
PYTHONPATH=src .venv/bin/python scripts/verify_foundry_agents.py
PYTHONPATH=src .venv/bin/python scripts/run_live_foundry_demo.py
```

The application uses the persisted definitions through the Responses API `agent_reference` contract. Set `FOUNDRY_USE_DEPLOYED_AGENTS=false` only for direct-model development.

## Container deployment

Run both services locally with one shared data volume:

```bash
docker compose up --build
```

The UI is available on port 8501 and the API on port 8000. The same image can run either service with `RAGTRUST_SERVICE=ui` or `RAGTRUST_SERVICE=api`. For a cloud deployment, supply credentials through the platform identity/environment and mount persistent storage at `/app/data`; never bake `.env` into the image.

The tests cover API behavior, end-to-end orchestration, wrong numbers, unsupported claims, incomplete answers, invalid citations, exact and semantic duplicates, valid abstention, evaluator calibration, bounded repair, linked revision attempts, immutable releases, extraction, and invalid media timestamps.

## Execution architecture

```text
Golden examples and source evidence
                 |
                 v
Dataset Understanding and Planning Agent
                 |
                 v
Generation Agent --> schema and exact duplicate checks
                 |
                 v
Independent Validation Agent
      | accepted | repairable | uncertain/rejected
      |          v            v
      |     Coverage and      Human review
      |     Refinement Agent
      |          |
      +----------+
                 v
Dataset-level metrics and immutable release
                 |
                 +--> JSONL, CSV, case assessments, HTML and JSON report
                 |
                 +--> optional separate RAG target evaluation
```

The application orchestrates four separately persisted Foundry prompt-agent definitions. They are versioned server-side assets, not four continuously running containers. Numerical aggregation, hashes, citation existence, duplicate rates, coverage, and distributions are computed by Python.

## Verified in this workspace

- Fixture-mode end-to-end generation, validation, repair, shortfall reporting, and release.
- FastAPI lifecycle through the test client.
- Four Foundry prompt agents deployed as version 1 and individually invoked successfully.
- Complete live Foundry run: 2 generated, 2 accepted, 100% topic coverage, zero duplicate pairs, and an immutable release.
- Application Insights/OpenTelemetry initialization.
- All automated tests listed above.

No additional Foundry resource or model deployment was provisioned. The Streamlit product is published on an HTTPS-only Azure App Service F1 plan in Canada Central and authenticates to the existing Foundry resource with a managed identity.
