# RAGTrust: upload and recording checklist

Historical document notice — this checklist preserves the September 26, 2026 submission snapshot and its earlier private hosted Foundry workflow. Its private-password, repository-upload, live-host, and 35-test statements describe that snapshot. The October 8 public launch configuration supersedes the hosted access instructions with anonymous temporary fixture sessions and disables Foundry. Public launch verification is pending. Use [the current README](../README.md) and [deployment manifest](DEPLOYMENT_MANIFEST.md) for publication status; course submission remains a separate user action.

Prepared 24 September 2026. The project files are prepared; the video and course submission still belong to you.

## Files to use

| Deliverable | Location in project | Purpose |
|---|---|---|
| Final report | `output/pdf/RAGTrust_Final_Report.pdf` | Architecture diagram, agent explanations, workflow, results, limitations |
| Complete submission bundle | `artifacts/RAGTrust_Submission_Bundle.zip` | Report, documentation, clean source ZIP, and measured evidence |
| Clean source | `artifacts/RAGTrust_Source.zip` | Upload or unpack into your own GitHub repository |
| Measured sample | `artifacts/RAGTrust_Live_Evidence.zip` | Five-file version-2 live dataset release |
| Recording narration | `docs/VIDEO_SCRIPT.md` | Suggested 5-7 minute screen recording |
| Reproduction and cloud receipt | `docs/DEPLOYMENT_MANIFEST.md` | Verified environment and explicit proof boundaries |

## Your remaining actions

1. Open the [live application](https://ragtrust-sainithin-public-2026.azurewebsites.net/). Sign in privately before recording. Your password is stored locally in `.private/demo-password.txt`; do not upload this file or display it in the video.
2. Read the final report and rehearse the video script. Use a small two-candidate run to conserve quota. Keep the included live evidence available if the free host cold-starts or a live call is delayed.
3. Record your screen and voice. Show golden examples, source evidence, the four Foundry agents, generation and verification, one case's citations, dataset metrics, and the five release files. Explain the limitations instead of claiming every blueprint feature is finished.
4. Open [the Founderz final activity](https://learn.founderz.com/lesson/final-activity-design-and-deliver-a-multi-agent-solution/294477ca-84d6-4c42-b258-b56fa24a331b) in your enrolled account. Check its current deadline, attachment sizes, required fields, and video length; these have not been reverified here.
5. Attach the final PDF. If ZIP files are accepted, attach the submission bundle. If the form requires a repository URL, publish the clean source ZIP contents to your own GitHub repository first. Add the app URL and your recorded video URL/file as requested by the form.
6. Share the demo password privately with reviewers only through an appropriate private channel if access is required. Never place it in a public repository, public document, public video, or ZIP.
7. Submit the form yourself and keep the success confirmation or receipt. Prepared files and a live app do not mean the course form was submitted.

## Safe summary to paste

RAGTrust is a text-first multi-agent application for generating and evaluating synthetic RAG evaluation datasets from trusted golden examples and source evidence. Four versioned Microsoft Foundry prompt agents plan, generate, independently verify, and repair cases under a Python orchestrator. It provides inspectable citations, bounded repair history, human review, transparent quality metrics, and immutable JSONL/CSV/report exports. The hosted Streamlit demo uses Azure App Service and the existing Foundry GPT-4o deployment. Thirty-five automated tests pass. The included two-case live release demonstrates the integration, not broad accuracy. Raw-media understanding, distributed resumable jobs, enterprise identity, and calibrated research-grade metrics remain future work.

## Final review

- [ ] Video recorded and reviewed; secrets are not visible.
- [ ] Repository/source and report links open for the intended reviewer.
- [ ] No `.env`, `.private`, access keys, runtime databases, or private uploads are included.
- [ ] No claim that Ragas, semantic retrieval metrics, raw-media understanding, or a representative human audit produced the current results.
- [ ] Founderz form requirements checked and final submission confirmation saved.
