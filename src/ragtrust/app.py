from __future__ import annotations

import json
import hmac
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ragtrust.config import settings
from ragtrust.db import PublicWorkspace, activate_workspace, init_db, session_scope
from ragtrust.models import (
    CandidateCase,
    DatasetVersion,
    EvidenceSegment,
    GenerationRun,
    GoldenExample,
    MetricAssessment,
    Project,
    QualityReport,
    RagRun,
    ReviewDecision,
    SourceAsset,
)
from ragtrust.orchestrator import OrchestrationService
from ragtrust.schemas import CaseStatus, GenerationConfig, RagEvalRequest, SourceMapping
from ragtrust.services.calibration import EvaluatorCalibrationEngine
from ragtrust.services.extractor import SourceExtractor, compute_sha256
from ragtrust.storage import LocalStorage

st.set_page_config(
    page_title="RAGTrust — Golden-Guided Synthetic Evaluation Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Clear any context left by an earlier script run before selecting this visitor.
activate_workspace(None)
if settings.public_demo:
    workspace = st.session_state.get("_public_workspace")
    if workspace is None or workspace.expired:
        st.session_state.clear()
        workspace = PublicWorkspace()
        st.session_state["_public_workspace"] = workspace
    activate_workspace(workspace)
    if "_public_service" not in st.session_state:
        st.session_state["_public_service"] = OrchestrationService()
    service = st.session_state["_public_service"]
else:
    init_db()
    service = OrchestrationService()
storage = LocalStorage()

if not settings.public_demo and settings.access_password and not st.session_state.get("authenticated"):
    st.title("RAGTrust")
    st.write("Generate evidence-grounded evaluation datasets with four Microsoft Foundry agents.")
    with st.form("demo_signin"):
        password = st.text_input("Demo access password", type="password")
        submitted = st.form_submit_button("Open workspace")
    if submitted:
        if hmac.compare_digest(password.encode(), settings.access_password.encode()):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("The password is incorrect.")
    st.caption("Private demonstration workspace. Request access from the project owner.")
    st.stop()

# Custom Styling
st.markdown(
    """
    <style>
    .main-header { font-size: 26px; font-weight: 700; color: inherit; margin-bottom: 2px; }
    .sub-header { font-size: 14px; color: inherit; opacity: 0.8; margin-bottom: 16px; }
    .metric-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; text-align: center; }
    .metric-val { font-size: 24px; font-weight: 700; color: #0f172a; }
    .metric-lbl { font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 6px; padding: 8px 16px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.markdown("### 🛡️ RAGTrust Platform")
    st.caption("Build evaluation datasets. Inspect and compare RAG responses.")
    if settings.public_demo:
        st.info("Free public demo · no sign-in required")
        st.caption("Your workspace is separate from other visitors. It expires after two hours or after this session is lost. Download your results before leaving.")
        if st.button("Reset my workspace", use_container_width=True):
            st.session_state.clear()
            activate_workspace(None)
            st.rerun()
    st.link_button("GitHub source", "https://github.com/Nithin9Krishna/ragtrust", use_container_width=True)
    st.divider()

    # Engine Mode Switcher
    st.markdown("#### ⚙️ Execution Engine")
    mode_choice = st.radio(
        "Agent Backend",
        options=["fixture"] if settings.public_demo else ["fixture", "foundry"],
        format_func=lambda x: "🧪 Fixture (Local & Offline)" if x == "fixture" else "☁️ Microsoft Foundry (Live gpt-4o)",
        index=0 if settings.public_demo or settings.mode == "fixture" else 1,
    )
    if mode_choice == "foundry":
        if settings.has_foundry_config:
            st.success(f"Configured: {settings.project_name or 'ragtrust-architect'}")
            trace_state = "App Insights configured" if settings.appinsights_connection_string else "App Insights not configured"
            st.caption(f"Model: {settings.model_deployment_name} • {trace_state}")
        else:
            st.error("Foundry endpoint is not configured. Select fixture mode or add the required environment settings; live runs fail closed and never masquerade as fixture output.")

    st.divider()

    # Project Selection
    st.markdown("#### 📁 Active Project")
    with session_scope() as session:
        projects = session.query(Project).order_by(Project.created_at.desc()).all()
        project_options = {p.id: f"{p.name} ({p.domain})" for p in projects}

    if not project_options:
        st.info("No projects yet. Create one or load demo data.")
        active_project_id = None
    else:
        active_project_id = st.selectbox(
            "Select Project",
            options=list(project_options.keys()),
            format_func=lambda pid: project_options[pid],
        )

    st.divider()
    # 1-Click Demo Loader
    st.markdown("#### 🚀 Quick Demo Setup")
    if st.button("Load IT Security Demo Data", use_container_width=True):
        demo_dir = Path(__file__).resolve().parent.parent.parent / "demo_data"
        p_id = service.create_project(
            name="IT Security & Compliance 2026",
            description="Golden Q&A benchmark for corporate security and regulatory compliance.",
            domain="cybersecurity_compliance",
        )
        # Ingest Golden CSV
        csv_path = demo_dir / "golden_support_qa.csv"
        if csv_path.exists():
            examples = SourceExtractor.parse_golden_file(csv_path.read_text(), csv_path.name)
            service.add_golden_examples(p_id, [e.model_dump() for e in examples])

        # Ingest Source Policy
        txt_path = demo_dir / "security_compliance_policy.txt"
        if txt_path.exists():
            txt_content = txt_path.read_text()
            segs = SourceExtractor.extract_text_segments(txt_content, "security_compliance_policy.txt", asset_id="")
            service.add_source_asset(
                p_id,
                "security_compliance_policy.txt",
                "text/plain",
                compute_sha256(txt_content),
                str(txt_path),
                segs,
            )

        # Ingest Video Transcript
        vid_path = demo_dir / "security_walkthrough_video.json"
        if vid_path.exists():
            vid_content = vid_path.read_text()
            v_segs = SourceExtractor.extract_text_segments(vid_content, "security_walkthrough_video.json", asset_id="")
            service.add_source_asset(
                p_id,
                "security_walkthrough_video.json",
                "application/json",
                compute_sha256(vid_content),
                str(vid_path),
                v_segs,
            )

        st.success("Loaded 30 Golden Q&As, Security Policy document, and Video Transcript!")
        st.rerun()

# Main Header
st.markdown('<div class="main-header">🛡️ RAGTrust — Golden-Guided Synthetic Evaluation Data Platform</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Autonomous multi-agent generation, independent claim validation, bounded repairs, and explainable dataset quality assurance.</div>', unsafe_allow_html=True)
if settings.public_demo:
    st.info("Start with **Load IT Security Demo Data** in the sidebar, generate a small dataset in **3. Run & Monitor**, release it in **7. Export & Release**, then compare your endpoint or recorded answers in **8. RAG Target Test**.")
    st.caption("Generation and verification use deterministic fixture rules in this public demo. RAG tests capture real endpoint or uploaded responses. Lexical overlap does not establish factual accuracy. Upload only non-confidential sample data; requests to your endpoint send dataset questions.")

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "1. Project & Ingest",
    "2. Profile & Plan",
    "3. Run & Monitor",
    "4. Case Inspector",
    "5. Dataset Quality",
    "6. Validate Evaluator",
    "7. Export & Release",
    "8. RAG Target Test",
])

# -----------------------------------------------------------------------------
# TAB 1: Project & Ingest
# -----------------------------------------------------------------------------
with tab1:
    st.subheader("Project Creation & Source Asset Ingestion")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Create New Project")
        with st.form("new_project_form"):
            p_name = st.text_input("Project Name", placeholder="e.g. Healthcare Policy Q&A")
            p_domain = st.text_input("Domain", placeholder="e.g. healthcare, legal, finance")
            p_desc = st.text_area("Purpose & Evaluation Goals", placeholder="Describe intended RAG evaluation scope...")
            if st.form_submit_button("Create Project"):
                if p_name.strip():
                    new_id = service.create_project(p_name.strip(), p_desc.strip(), p_domain.strip() or "general")
                    st.success(f"Project created with ID: {new_id}")
                    st.rerun()
                else:
                    st.error("Project name is required.")

    with col2:
        st.markdown("#### Ingest Golden Examples & Sources")
        if not active_project_id:
            st.info("Select or create a project first.")
        else:
            with session_scope() as session:
                golden_count = session.query(GoldenExample).filter_by(project_id=active_project_id).count()
                source_count = session.query(SourceAsset).filter_by(project_id=active_project_id).count()
                seg_count = session.query(EvidenceSegment).join(SourceAsset).filter(SourceAsset.project_id == active_project_id).count()

            m1, m2, m3 = st.columns(3)
            m1.metric("Golden Examples", golden_count)
            m2.metric("Source Assets", source_count)
            m3.metric("Evidence Segments", seg_count)

            # Upload Golden CSV/JSONL
            uploaded_golden = st.file_uploader("Upload Golden Examples (CSV / JSONL)", type=["csv", "jsonl", "json"])
            if uploaded_golden:
                content = uploaded_golden.read()
                parsed = SourceExtractor.parse_golden_file(content, uploaded_golden.name)
                st.caption(f"Parsed {len(parsed)} examples.")
                if st.button("Import Golden Examples"):
                    added = service.add_golden_examples(active_project_id, [e.model_dump() for e in parsed])
                    st.success(f"Imported {added} examples!")
                    st.rerun()

            # Upload Source Doc
            uploaded_doc = st.file_uploader("Upload Source Material (TXT / PDF / Video JSON)", type=["txt", "pdf", "json", "vtt"])
            if uploaded_doc:
                doc_content = uploaded_doc.read()
                doc_sha = compute_sha256(doc_content)
                segments = SourceExtractor.extract_text_segments(doc_content, uploaded_doc.name, asset_id="")
                st.caption(f"Extracted {len(segments)} evidence segments.")
                if st.button("Register Source Material"):
                    stored_path, stored_sha = storage.put(active_project_id, "sources", uploaded_doc.name, doc_content)
                    scanned_pdf = uploaded_doc.name.lower().endswith(".pdf") and not segments
                    aid = service.add_source_asset(
                        active_project_id,
                        uploaded_doc.name,
                        uploaded_doc.type or "text/plain",
                        stored_sha,
                        stored_path,
                        segments,
                        extraction_status="needs_ocr" if scanned_pdf else "completed",
                        extraction_notes=(
                            "No extractable PDF text was found. OCR is required; no content was fabricated."
                            if scanned_pdf else f"Extracted {len(segments)} evidence segments."
                        ),
                    )
                    if scanned_pdf:
                        st.warning("Registered the original PDF, but it requires OCR before it can be used as evidence.")
                    else:
                        st.success(f"Registered source asset with {len(segments)} segments!")
                    st.rerun()

# -----------------------------------------------------------------------------
# TAB 2: Profile & Plan
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("Dataset Understanding & Coverage Planning")
    if not active_project_id:
        st.info("Select a project first.")
    else:
        with session_scope() as session:
            golden = session.query(GoldenExample).filter_by(project_id=active_project_id).all()
            evidence = session.query(EvidenceSegment).join(SourceAsset).filter(SourceAsset.project_id == active_project_id).all()

        st.markdown("Configure your generation and quality requirements:")
        c1, c2, c3, c4 = st.columns(4)
        c_target = c1.number_input("Candidate Target", min_value=2, max_value=settings.max_candidates, value=min(4, settings.max_candidates))
        a_target = c2.number_input("Accepted Target", min_value=1, max_value=int(c_target), value=min(2, int(c_target)))
        max_rep = c3.number_input("Max Repairs per Case", min_value=0, max_value=settings.max_repairs, value=min(1, settings.max_repairs))
        budget = c4.number_input("Candidate budget units", min_value=2, max_value=1000, value=20)

        gen_config = GenerationConfig(
            candidate_target=c_target,
            accepted_target=a_target,
            max_repairs=max_rep,
            budget_units=budget,
        )

        if st.button("Run Planning Agent", type="primary"):
            with st.spinner("Dataset Understanding Agent is analyzing golden data and source evidence..."):
                golden_dicts = [{"id": g.id, "question": g.question, "trusted_answer": g.trusted_answer, "topic": g.topic} for g in golden]
                ev_dicts = [{"id": e.id, "locator": e.locator, "text": e.text} for e in evidence]
                plan = service.planner.run(
                    {"golden_examples": golden_dicts, "evidence_segments": ev_dicts, "config": gen_config, "domain": "security"},
                    mode=mode_choice,
                )
                st.session_state[f"plan_{active_project_id}"] = plan

        if f"plan_{active_project_id}" in st.session_state:
            plan = st.session_state[f"plan_{active_project_id}"]
            st.success("Coverage Plan Created!")

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.markdown("#### Topic Quotas")
                quotas = plan.get("topic_quotas", {})
                st.bar_chart(pd.DataFrame(list(quotas.items()), columns=["Topic", "Quota"]).set_index("Topic"))

            with col_p2:
                st.markdown("#### Gaps & Inconsistencies Detected")
                gaps = plan.get("detected_gaps", [])
                conflicts = plan.get("source_conflicts", [])
                if gaps:
                    for g in gaps:
                        st.warning(f"⚠️ {g}")
                else:
                    st.info("No unaddressed topic gaps detected in source corpus.")

                if conflicts:
                    for cf in conflicts:
                        st.error(f"🚨 {cf}")

# -----------------------------------------------------------------------------
# TAB 3: Run & Monitor
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("Multi-Agent Generation & Validation Pipeline")
    if not active_project_id:
        st.info("Select a project first.")
    else:
        st.markdown(
            "Execute the orchestrated pipeline: **Generation Agent** -> **Exact Deduplication** -> **Independent Validation Agent** -> **Refinement Repair Agent** (bounded retries)."
        )

        with st.form("generation_configuration"):
            cfg1, cfg2, cfg3 = st.columns(3)
            candidate_target = cfg1.number_input("Candidate target", min_value=1, max_value=settings.max_candidates, value=min(4, settings.max_candidates))
            accepted_target = cfg2.number_input("Accepted target", min_value=1, max_value=settings.max_candidates, value=2)
            repair_limit = cfg3.number_input("Repair limit per case", min_value=0, max_value=settings.max_repairs, value=min(1, settings.max_repairs))
            language = st.text_input("Output language", value="English")
            budget_units = st.number_input("Candidate budget units (2 units per candidate; not currency)", min_value=2, value=20)
            quotas_json = st.text_area("Optional approved topic quotas (JSON; sum must equal candidate target)", value="{}")
            start_run = st.form_submit_button("Start Generation & Verification Run", type="primary")
        if start_run:
            try:
                plan_config = GenerationConfig(candidate_target=candidate_target, accepted_target=accepted_target,
                    max_repairs=repair_limit, language=language, budget_units=budget_units,
                    topic_quotas=json.loads(quotas_json))
                run_id = service.enqueue_generation_run(active_project_id, plan_config, mode=mode_choice)
                st.session_state["active_run_id"] = run_id
                st.success("Run queued. Refresh progress below to inspect its status.")
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
        st.button("Refresh run progress")

        # Show run history and details
        with session_scope() as session:
            runs = session.query(GenerationRun).filter_by(project_id=active_project_id).order_by(GenerationRun.created_at.desc()).all()

        if runs:
            st.divider()
            st.markdown("#### Run Summary & Live Metrics")
            selected_run = runs[0]
            run_summary = selected_run.progress_json or {}
            st.write(f"Run status: {selected_run.status} | Mode: {selected_run.mode} | ID: {selected_run.id}")
            if selected_run.error:
                st.error(f"Run failed: {selected_run.error}")
            if selected_run.status in {"queued", "running"} and st.button("Cancel active run"):
                service.cancel_generation_run(selected_run.id)
                st.info("Cancellation requested; the active model call will finish first.")

            r1, r2, r3, r4, r5, r6 = st.columns(6)
            r1.metric("Generated", run_summary.get("generated", 0))
            r2.metric("Accepted", run_summary.get("accepted", 0))
            r3.metric("Repaired", run_summary.get("repairs", 0))
            r4.metric("Rejected", run_summary.get("rejected", 0))
            r5.metric("Review Needed", run_summary.get("needs_review", 0))
            r6.metric("Shortfall", run_summary.get("shortfall", 0))

            if run_summary.get("limitations"):
                with st.expander("Auditor Disclosures & Notes", expanded=True):
                    for lim in run_summary.get("limitations", []):
                        st.info(f"ℹ️ {lim}")

# -----------------------------------------------------------------------------
# TAB 4: Case Inspector & Review
# -----------------------------------------------------------------------------
with tab4:
    st.subheader("Case-Level Evidence & Claim Verification Inspector")
    with session_scope() as session:
        all_cases = session.query(CandidateCase).filter_by(project_id=active_project_id).order_by(CandidateCase.created_at.desc()).all()

    if not all_cases:
        st.info("No candidate cases generated yet.")
    else:
        filter_col1, filter_col2 = st.columns(2)
        status_filter = filter_col1.selectbox("Filter Status", ["All", "accepted", "needs_revision", "needs_review", "rejected"])
        modality_filter = filter_col2.selectbox("Filter Modality", ["All", "text", "video"])

        filtered = all_cases
        if status_filter != "All":
            filtered = [c for c in filtered if c.status == status_filter]
        if modality_filter != "All":
            filtered = [c for c in filtered if c.modality == modality_filter]

        st.caption(f"Displaying {len(filtered)} cases.")

        for c in filtered[:10]:
            with st.expander(f"[{c.status.upper()}] Case {c.id[:8]}: {c.question[:80]}...", expanded=(c.status != "accepted")):
                c_col1, c_col2 = st.columns([3, 2])
                with c_col1:
                    st.markdown(f"**Question:** {c.question}")
                    st.markdown(f"**Candidate Reference Answer:** {c.candidate_reference_answer}")
                    st.caption(f"Topic: {c.topic} • Scenario: {c.scenario_type} • Difficulty: {c.difficulty} • Modality: {c.modality}")
                    st.caption(f"Evidence References: `{c.evidence_refs}`")

                with c_col2:
                    with session_scope() as session:
                        assessments = session.query(MetricAssessment).filter_by(case_id=c.id).all()

                    for a in assessments:
                        st.markdown(f"**{a.metric_name}:** `{a.score}` ({a.concise_reason})")

                    if c.failed_checks:
                        st.error(f"Failed Claims / Checks: {c.failed_checks}")

                # Human Override & Review
                st.markdown("---")
                rev_col1, rev_col2, rev_col3 = st.columns([1, 1, 2])
                if rev_col1.button("✅ Approve", key=f"app_{c.id}"):
                    service.review_case(c.id, "approve", notes="Manually verified by reviewer")
                    st.success("Approved!")
                    st.rerun()
                if rev_col2.button("❌ Reject", key=f"rej_{c.id}"):
                    service.review_case(c.id, "reject", notes="Rejected by reviewer")
                    st.warning("Rejected!")
                    st.rerun()
                with rev_col3:
                    correct_text = st.text_input("Correct Answer", placeholder="Type corrected answer...", key=f"cor_{c.id}")
                    if st.button("Submit Correction", key=f"btn_cor_{c.id}"):
                        if correct_text.strip():
                            service.review_case(c.id, "correct", corrected_answer=correct_text.strip(), notes="Auditor manual override")
                            st.success("Answer corrected and approved!")
                            st.rerun()

# -----------------------------------------------------------------------------
# TAB 5: Dataset Quality & Analytics
# -----------------------------------------------------------------------------
with tab5:
    st.subheader("Dataset-Level Quality & Diversity Analytics")
    with session_scope() as session:
        last_run = session.query(GenerationRun).filter_by(project_id=active_project_id).order_by(GenerationRun.created_at.desc()).first()

    if not last_run or not last_run.progress_json:
        st.info("Run generation to view dataset-level analytics.")
    else:
        ds_metrics = last_run.progress_json.get("dataset_metrics", {})
        tc = ds_metrics.get("topic_coverage", {})
        dupe_rate = ds_metrics.get("exact_duplicate_rate", 0.0)
        sem_dupes = ds_metrics.get("semantic_duplicate_pairs", [])
        js_div = ds_metrics.get("jensen_shannon_divergence", 0.0)
        avg_faith = ds_metrics.get("avg_faithfulness")

        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Topic Coverage", f"{tc.get('coverage_ratio', 1.0)*100:.1f}%", f"{tc.get('met_topics',0)}/{tc.get('total_topics',0)} met")
        q2.metric("Exact Duplicates", f"{dupe_rate*100:.1f}%", "Hash collisions")
        q3.metric("JS Distribution Distance", f"{js_div:.4f}", "Target vs Accepted")
        q4.metric("Avg Faithfulness", f"{avg_faith:.3f}" if avg_faith is not None else "Not assessed", "Accepted-case claim support")

        st.divider()
        col_q1, col_q2 = st.columns(2)
        with col_q1:
            st.markdown("#### Topic Target vs Actual")
            breakdown = tc.get("breakdown", {})
            if breakdown:
                df_topic = pd.DataFrame(
                    [{"Topic": t, "Target": d["target"], "Actual": d["actual"]} for t, d in breakdown.items()]
                ).set_index("Topic")
                st.bar_chart(df_topic)

        with col_q2:
            st.markdown("#### Redundancy Analysis")
            if sem_dupes:
                st.warning(f"Detected {len(sem_dupes)} lexical near-duplicate pair(s) with similarity >= 0.82:")
                for p in sem_dupes[:3]:
                    st.caption(f"**Sim: {p['similarity']}** • '{p['text_1']}' vs '{p['text_2']}'")
            else:
                st.success("Zero lexical near-duplicates detected above the configured threshold.")

# -----------------------------------------------------------------------------
# TAB 6: Evaluator Calibration
# -----------------------------------------------------------------------------
with tab6:
    st.subheader("Validate the Evaluator — Calibration Benchmark")
    st.markdown(
        "A trustworthy evaluation system must measure its own judge reliability. "
        "Here we test the independent Validation Agent against human-labelled ground-truth cases containing known defects."
    )

    if st.button("Run Evaluator Calibration Benchmark", type="primary"):
        demo_dir = Path(__file__).resolve().parent.parent.parent / "demo_data"
        bench_path = demo_dir / "calibration_benchmark.json"
        if bench_path.exists():
            cases = json.loads(bench_path.read_text())
            def eval_fn(case):
                return service.verifier.run(
                    {
                        "question": case.get("question"),
                        "candidate_reference_answer": case.get("candidate_reference_answer"),
                        "expected_behavior": case.get("expected_behavior", "answer"),
                        "evidence_segments": case.get("evidence_segments", []),
                        "evidence_refs": case.get("evidence_refs", []),
                        "valid_locators": set(case.get("valid_locators", ["policy.txt:sec1", "policy.txt:sec2", "policy.txt:sec3", "policy.txt:sec4", "policy.txt:sec5", "policy.txt:sec6"])),
                        "required_facts": case.get("required_facts", []),
                    },
                    mode=mode_choice,
                )

            calib_res = EvaluatorCalibrationEngine.evaluate_benchmark(cases, eval_fn)
            st.session_state["calibration_result"] = calib_res

    if "calibration_result" in st.session_state:
        c_res = st.session_state["calibration_result"]
        st.success(f"Calibration Complete across {c_res.total_cases} ground-truth benchmark cases!")

        cm = c_res.confusion_matrix
        m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
        m_c1.metric("Judge Accuracy", f"{c_res.accuracy*100:.1f}%")
        m_c2.metric("Defect Precision", f"{c_res.defect_precision*100:.1f}%")
        m_c3.metric("Defect Recall", f"{c_res.defect_recall*100:.1f}%")
        m_c4.metric("Defect F1", f"{c_res.defect_f1*100:.1f}%")
        m_c5.metric("Cohen's Kappa (κ)", f"{c_res.cohens_kappa:.3f}")

        # Confusion matrix visual table
        st.markdown("#### Confusion Matrix (Defect Detection)")
        cm_df = pd.DataFrame(
            [
                {"Actual": "Defective", "Predicted Defective": cm["TP"], "Predicted Valid": cm["FN"]},
                {"Actual": "Valid", "Predicted Defective": cm["FP"], "Predicted Valid": cm["TN"]},
            ]
        ).set_index("Actual")
        st.dataframe(cm_df, use_container_width=True)

        st.markdown("#### Case-by-Case Evaluator Explanations")
        for d in c_res.details:
            badge = "🟢" if "TP" in d["outcome"] or "TN" in d["outcome"] else "🔴"
            st.markdown(
                f"{badge} **{d['case_id']}** ({d['defect_type']}) &bull; Outcome: `{d['outcome']}` &bull; Predicted: `{d['predicted_status']}` &bull; *Reason:* {d['reason']}"
            )

# -----------------------------------------------------------------------------
# TAB 7: Export & Release Center
# -----------------------------------------------------------------------------
with tab7:
    st.subheader("Versioned Export & Immutable Release Center")
    with session_scope() as session:
        runs = session.query(GenerationRun).filter_by(project_id=active_project_id).filter(GenerationRun.status.in_(["completed", "completed_shortfall"])).order_by(GenerationRun.created_at.desc()).all()
        versions = session.query(DatasetVersion).filter_by(project_id=active_project_id).order_by(DatasetVersion.created_at.desc()).all()

    if not runs:
        st.info("Execute a generation run first.")
    else:
        st.markdown("#### Freeze Approved Dataset Release")
        selected_run_to_release = st.selectbox("Select Completed Run", [r.id for r in runs])
        if st.button("🔒 Freeze & Release Dataset Version", type="primary"):
            new_v_id = service.release_dataset_version(selected_run_to_release)
            st.success(f"Released Dataset Version with ID: {new_v_id}!")
            st.rerun()

    if versions:
        st.divider()
        st.markdown("#### Published Releases & Artifacts")
        for v in versions:
            with st.expander(f"📦 Version {v.version_number} (Released {v.created_at.strftime('%Y-%m-%d %H:%M')})", expanded=True):
                manifest = v.manifest_json or {}
                files = manifest.get("files", {})
                jsonl_path = files.get("jsonl", {}).get("path")
                csv_path = files.get("csv", {}).get("path")

                st.markdown(f"**Total Accepted Cases:** `{manifest.get('total_accepted_cases', 0)}`")
                st.markdown(f"**JSONL SHA256:** `{manifest.get('files', {}).get('jsonl', {}).get('sha256', '')}`")
                st.markdown(f"**CSV SHA256:** `{manifest.get('files', {}).get('csv', {}).get('sha256', '')}`")

                d_col1, d_col2, d_col3 = st.columns(3)
                if jsonl_path and Path(jsonl_path).exists():
                    d_col1.download_button(
                        "📥 Download JSONL",
                        data=Path(jsonl_path).read_bytes(),
                        file_name=f"ragtrust_dataset_v{v.version_number}.jsonl",
                        mime="application/jsonlines",
                    )
                if csv_path and Path(csv_path).exists():
                    d_col2.download_button(
                        "📊 Download CSV",
                        data=Path(csv_path).read_bytes(),
                        file_name=f"ragtrust_dataset_v{v.version_number}.csv",
                        mime="text/csv",
                    )

                with session_scope() as session:
                    qr = session.query(QualityReport).filter_by(dataset_version_id=v.id).first()

                if qr and Path(qr.html_path).exists():
                    d_col3.download_button(
                        "📄 Download Quality Report (HTML)",
                        data=Path(qr.html_path).read_bytes(),
                        file_name=f"ragtrust_quality_report_v{v.version_number}.html",
                        mime="text/html",
                    )
                assessment_path = files.get("case_assessments", {}).get("path")
                if assessment_path and Path(assessment_path).exists():
                    st.download_button("Download all case assessments", Path(assessment_path).read_bytes(),
                        file_name=f"assessments_v{v.version_number}.jsonl", key=f"assessments_{v.id}")
                if qr and Path(qr.json_path).exists():
                    st.download_button("Download machine-readable summary", Path(qr.json_path).read_bytes(),
                        file_name=f"summary_v{v.version_number}.json", key=f"summary_{v.id}")

# -----------------------------------------------------------------------------
# TAB 8: RAG Target Testing
# -----------------------------------------------------------------------------
with tab8:
    st.subheader("Optional: Test Deployed RAG Endpoint")
    st.markdown(
        "Evaluate a live deployed RAG endpoint using the frozen golden-guided evaluation dataset. "
        "Test queries are sent without ground-truth reference leakage, and endpoint metrics are kept completely distinct from dataset quality."
    )

    with session_scope() as session:
        released_versions = session.query(DatasetVersion).filter_by(project_id=active_project_id).order_by(DatasetVersion.created_at.desc()).all()

    if not released_versions:
        st.info("Release an approved dataset version in Tab 7 first.")
    else:
        v_select = st.selectbox("Select Approved Dataset Version", [v.id for v in released_versions], format_func=lambda x: f"Version {x[:8]}")
        endpoint_url = st.text_input("RAG Endpoint URL (Optional)", placeholder="https://my-rag-service.azurewebsites.net/api/query")
        recorded = st.text_area("Or recorded responses as a JSON question-to-answer mapping", value="{}")
        demo_mode = st.checkbox("Use clearly labelled fixture responses (demonstration only)", value=False)

        st.caption('Endpoint contract: public HTTPS on port 443; POST {"query": "your question"}; return {"answer": "your answer"} or {"response": "your answer"}. Redirects and private network addresses are rejected.')
        response_file = st.file_uploader("Upload recorded responses (JSON question-to-answer mapping)", type=["json"], key="rag_recorded_responses")
        if st.button("Run RAG Endpoint Evaluation"):
            with st.spinner("Executing RAG evaluation queries..."):
                try:
                    req = RagEvalRequest(
                        endpoint_url=endpoint_url.strip() or None,
                        endpoint_label="Configured endpoint" if endpoint_url else "Recorded or fixture responses",
                        mock_responses=json.loads(response_file.getvalue() if response_file else recorded),
                        demo_mode=demo_mode,
                    )
                    rag_results = service.run_rag_test(v_select, req)
                    st.session_state[f"rag_results_{active_project_id}"] = rag_results
                except ValueError as exc:
                    st.error(str(exc))

        if f"rag_results_{active_project_id}" in st.session_state:
            rr = st.session_state[f"rag_results_{active_project_id}"]
            st.success(f"Evaluated {rr.get('total_cases_evaluated')} queries against target system!")
            st.info(f"Evaluation mode: {rr.get('evaluation_mode')}; failed responses: {rr.get('errors')}")
            for limitation in rr.get("limitations", []):
                st.caption(limitation)

            rag_m1, rag_m2, rag_m3, rag_m4 = st.columns(4)
            overlap = rr.get("avg_reference_token_recall")
            abstention = rr.get("abstention_accuracy")
            rag_m1.metric("Reference token recall", f"{overlap*100:.1f}%" if overlap is not None else "Not assessed")
            rag_m2.metric("Semantic quality", "Not assessed")
            rag_m3.metric("Abstention phrase match", f"{abstention*100:.1f}%" if abstention is not None else "Not assessed")
            rag_m4.metric("Avg Latency", f"{rr.get('avg_latency_ms', 0):.1f} ms")

            st.markdown("#### Captured Responses and Lexical Comparison")
            df_rag = pd.DataFrame(rr.get("results", []))
            st.dataframe(df_rag, use_container_width=True)
