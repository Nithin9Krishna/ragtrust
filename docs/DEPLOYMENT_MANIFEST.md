# RAGTrust Deployment Manifest

Verified on: 2026-09-22

## Public application

- URL: https://ragtrust-sainithin-public-2026.azurewebsites.net/
- Azure resource group: `rg-ssainithinkrishna-9845`
- Web app: `ragtrust-sainithin-public-2026`
- App Service plan: `ragtrust-free-canada`
- Region: Canada Central
- Tier: F1 Free
- Runtime: Python 3.11 on Linux
- HTTPS only: enabled
- Service mode: Streamlit UI
- Persistent working path: `/home/data`

## Foundry integration

- Foundry account: `ragtrust-foundry-sweden`
- Foundry project: `ragtrust-architect`
- Model deployment: `gpt-4o`
- Web app authentication: system-assigned managed identity
- RBAC: Cognitive Services User scoped to the existing Foundry account
- Application Insights: configured
- Prompt content capture: disabled

Persisted prompt agents:

| Application role | Foundry asset | Version |
|---|---|---:|
| Dataset Understanding and Planning | `ragtrust-dataset-understanding` | 1 |
| Generation | `ragtrust-generation` | 1 |
| Independent Verification | `ragtrust-independent-verification` | 1 |
| Coverage and Refinement | `ragtrust-coverage-refinement` | 1 |

## Verification record

- Public health endpoint returned `ok`.
- Public Streamlit interface rendered the complete eight-stage UI.
- UI displayed `Connected: ragtrust-architect`, `Model: gpt-4o`, and `App Insights configured`.
- Every persisted prompt agent returned schema-compatible JSON in a live smoke test.
- Complete live local-to-Foundry run ID: `c508ab1b-a8ac-4cb0-9681-7608717837d5`.
- Released live dataset version: `ac1c38a3-97cc-49e7-bd76-d8fbee4e1d5a`.
- Live result: 2 generated, 2 accepted, 100% topic coverage, zero exact duplicates, zero semantic duplicate pairs, average accepted-case faithfulness 1.0.
- Automated suite: 26 passed.

## Deployable artifacts

- `artifacts/ragtrust-deploy.zip`: Azure source deployment package.
- `artifacts/ragtrust-submission.zip`: clean repository/submission package including tests and documentation.
- `Dockerfile` and `docker-compose.yml`: UI/API container package.

The archives intentionally exclude `.env`, access tokens, connection strings, local databases, generated uploads/releases, caches, and the virtual environment.

## Scope note

The free single-instance deployment is suitable for demonstration and judging. It keeps SQLite data under `/home/data`, but it is not a horizontally scalable production topology. The repository documents the managed database, blob storage, and distributed queue upgrades required for enterprise scale.
