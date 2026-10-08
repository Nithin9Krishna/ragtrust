# RAGTrust Deployment Manifest

Public launch preparation: 2026-10-08 (America/Chicago). Publication and hosted verification are pending; no completed launch is claimed by this manifest yet.

## October 8 public launch configuration

- Planned repository: https://github.com/Nithin9Krishna/ragtrust
- Demo URL: https://ragtrust-sainithin-public-2026.azurewebsites.net/
- Hosting: existing Azure App Service F1 Free Linux/Python 3.11 plan in Canada Central; no plan upgrade.
- Service: anonymous Streamlit UI with `RAGTRUST_PUBLIC_DEMO=true` and `RAGTRUST_MODE=fixture`.
- Inference: deterministic fixtures for planning, generation, verification, and repair. Foundry calls are blocked at the client boundary.
- Storage: separate `TemporaryDirectory` and SQLite database for each browser session, including its uploads and releases.
- Session lifetime: capped at two hours; resets on the next interaction after expiry. Disconnected session reconnect window: 120 seconds.
- Public limits: 20 candidates per run, one repair per case, and 5 MB per upload.
- API: no separately hosted public API; public mode blocks FastAPI routes except `/health`.
- Optional target tests: recorded responses or public HTTPS endpoints on port 443. Endpoint requests pin a validated public address, preserve the original Host header/TLS server name, bypass proxies, reject redirects, and limit response bodies to 1 MiB.
- Data guidance: non-confidential demonstration inputs only. Download exports before leaving; session storage is temporary.

## Public launch verification record

Pending: clean public repository publication, deployment of the fixture configuration, anonymous browser access, independent session workspaces, sample generation/release, downloads, and recorded-response comparison. The suite includes session-isolation and endpoint transport tests; current run results are pending. The free host can cold-start or exhaust its allowance.

## September 26 historical submission snapshot

The remaining sections preserve the earlier private hosted configuration and measured Foundry evidence. They do not establish the October 8 public launch state. The private-password and persistent-workspace instructions are superseded for the public host. Optional local/private Foundry use remains supported by the source.

Historical final handoff review: 2026-09-26 (America/Chicago).

### Historical application configuration

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
- Workspace access: private demonstration password; not multi-tenant authentication
- API: packaged and tested locally, not separately hosted publicly

### Historical Foundry integration

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
| Dataset Understanding and Planning | `ragtrust-dataset-understanding` | 2 |
| Generation | `ragtrust-generation` | 2 |
| Independent Verification | `ragtrust-independent-verification` | 2 |
| Coverage and Refinement | `ragtrust-coverage-refinement` | 2 |

### Historical verification record

- Public Streamlit health endpoint `/_stcore/health` returned `ok`.
- Public Streamlit interface rendered the complete eight-stage UI.
- The private login was exercised successfully; the cloud sample loader created 30 golden examples, 2 source assets, and 12 evidence segments.
- UI displayed `Configured: ragtrust-architect`, `Model: gpt-4o`, and `App Insights configured`. Configuration labels alone are not proof of inference or received traces.
- All four version-1 roles previously returned schema-compatible JSON in individual live smoke tests, including repair. Current definitions and runtime pin are version 2.
- Complete live local-to-Foundry run ID: `f1a2ff2f-cde8-45d0-8e26-186af813b0bc`.
- Released live dataset version: `d4957234-bbda-4a2a-81b9-f4640dccf444`.
- Live result: 2 generated, 2 accepted, both topic quotas met, zero exact duplicates, zero lexical near-duplicate pairs, average accepted-case faithfulness 1.0. No repair was required in this run.
- The explicit `foundry_agent_version` provenance field is `2`; the internal prompt-pack label is a separate identifier.
- Automated suite: 35 passed, one dependency deprecation warning.

The two-case evidence is an integration test, not a general accuracy benchmark. Human-audited correctness remains unassessed. Cloud-hosted inference verification is recorded below separately; local-to-Foundry testing must not be described as a browser-to-cloud run.

### Historical deployable artifacts

Azure deployment `ce8443b3-69d4-4696-8696-a81720906163` completed successfully (`status=4`, `complete=true`) at `2026-09-25T12:23:01Z`. The deployed archive's 24 Python runtime files were checked against the local source snapshot with no differences.

Two browser-started cloud runs (`eaee576b-5176-4fff-ad1a-4d0773ef48a1` and `81e16cf4-a5f4-4293-b354-7df1a0b01ca6`) failed closed after Foundry returned failed-claim explanations as objects instead of text. The final adapter preserves structured failure details as text before schema validation, without dropping the failure or accepting it. An earlier pre-validation step was also removed so the normalization runs first. The regression is tested through the live adapter's response-parsing path. This final deployment contains both corrections.

- `artifacts/ragtrust-deploy.zip`: Azure source deployment package.
- `artifacts/RAGTrust_Source.zip`: clean repository package including tests and documentation.
- `artifacts/RAGTrust_Live_Evidence.zip`: measured five-file live release.
- `artifacts/RAGTrust_Submission_Bundle.zip`: source, measured evidence, final PDF, and supporting documents.
- `artifacts/SHA256SUMS.txt`: final handoff archive checksums.
- `Dockerfile` and `docker-compose.yml`: UI/API container package.

The source archive excludes `.env`, `.private`, access tokens, connection strings, local databases, uploaded private files, caches, and the virtual environment. The evidence archive deliberately contains only the selected synthetic live demonstration release. No video is included and no course submission or GitHub publication has been performed.

### Historical scope note

The free single-instance deployment is suitable for demonstration and judging. It keeps SQLite data under `/home/data`, but it is not a horizontally scalable production topology. The repository documents the managed database, blob storage, and distributed queue upgrades required for enterprise scale.
