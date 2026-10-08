"""Build the attachment-ready public user manual.

Install ReportLab and Pillow, then run ``python scripts/build_user_manual.py``.
The PDF is written to output/pdf; the published copy is under docs.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable, Image, KeepTogether, PageBreak, Paragraph, Preformatted,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/RAGTrust_User_Manual.pdf"
SITE = "https://ragtrust-sainithin-public-2026.azurewebsites.net/"
REPO = "https://github.com/Nithin9Krishna/ragtrust"
NAVY = colors.HexColor("#09263F")
AMBER = colors.HexColor("#F3B756")
PAPER = colors.HexColor("#FBF8F0")
MUTED = colors.HexColor("#526475")
LINE = colors.HexColor("#DCE3E8")
PALE = colors.HexColor("#EDF4F8")
WIDTH = 516

font_root = Path("/System/Library/Fonts/Supplemental")
if (font_root / "Arial.ttf").exists():
    pdfmetrics.registerFont(TTFont("ManualSans", str(font_root / "Arial.ttf")))
    pdfmetrics.registerFont(TTFont("ManualSans-Bold", str(font_root / "Arial Bold.ttf")))
    pdfmetrics.registerFontFamily("ManualSans", normal="ManualSans", bold="ManualSans-Bold", italic="ManualSans", boldItalic="ManualSans-Bold")
    FONT, BOLD = "ManualSans", "ManualSans-Bold"
else:
    FONT, BOLD = "Helvetica", "Helvetica-Bold"

STYLES = {
    "body": ParagraphStyle("Body", fontName=FONT, fontSize=10.5, leading=15, textColor=NAVY, spaceAfter=7),
    "small": ParagraphStyle("Small", fontName=FONT, fontSize=9, leading=12.5, textColor=MUTED, spaceAfter=7),
    "title": ParagraphStyle("Title", fontName=BOLD, fontSize=27, leading=32, textColor=NAVY, spaceAfter=12),
    "heading": ParagraphStyle("Heading", fontName=BOLD, fontSize=12.5, leading=16, textColor=NAVY, spaceBefore=10, spaceAfter=7),
    "eyebrow": ParagraphStyle("Eyebrow", fontName=BOLD, fontSize=9, leading=12, textColor=MUTED, spaceAfter=7),
    "cell": ParagraphStyle("Cell", fontName=FONT, fontSize=9.3, leading=13, textColor=NAVY),
    "cellhead": ParagraphStyle("CellHead", fontName=BOLD, fontSize=9.3, leading=13, textColor=colors.white),
    "code": ParagraphStyle("Code", fontName="Courier", fontSize=8.4, leading=12, textColor=NAVY),
}


def p(text, style="body"):
    return Paragraph(text, STYLES[style])


def heading(text):
    return p(text, "heading")


def table(headers, rows, widths):
    cells = [[p(escape(x), "cellhead") for x in headers]]
    cells += [[p(x, "cell") for x in row] for row in rows]
    result = Table(cells, colWidths=widths, hAlign="LEFT", repeatRows=1)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, LINE),
    ]))
    return result


def note(title, text):
    box = Table([[p(f"<b>{title}</b><br/>{text}")]], colWidths=[WIDTH], hAlign="LEFT")
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#E9D5B2")),
        ("LEFTPADDING", (0, 0), (-1, -1), 13),
        ("RIGHTPADDING", (0, 0), (-1, -1), 13),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return KeepTogether([Spacer(1, 7), box, Spacer(1, 9)])


def code(text):
    box = Table([[Preformatted(text, STYLES["code"])]], colWidths=[WIDTH])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return KeepTogether([box, Spacer(1, 9)])


def step(number, title, text):
    block = Table([[p(f"<font color='#AD741E'><b>{number:02d}</b></font>"), p(f"<b>{title}</b><br/>{text}")]], colWidths=[35, WIDTH - 35])
    block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether([block])


class Workflow(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = WIDTH, 62

    def draw(self):
        labels = ["1. Inputs", "2. Generate", "3. Review", "4. Release", "5. RAG test"]
        box_width, gap = 96, 9
        for index, label in enumerate(labels):
            x = index * (box_width + gap)
            self.canv.setFillColor(PALE if index != 4 else AMBER)
            self.canv.roundRect(x, 15, box_width, 34, 6, stroke=0, fill=1)
            self.canv.setFillColor(NAVY)
            self.canv.setFont(BOLD, 9.5)
            self.canv.drawCentredString(x + box_width / 2, 27, label)
            if index < 4:
                self.canv.setStrokeColor(MUTED)
                self.canv.line(x + box_width + 1, 32, x + box_width + gap - 1, 32)


def qr(url, size=72):
    widget = QrCodeWidget(url)
    x, y, right, top = widget.getBounds()
    drawing = Drawing(size, size, transform=[size/(right-x), 0, 0, size/(top-y), 0, 0])
    drawing.add(widget)
    return drawing


def page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PAPER if doc.page == 1 else colors.white)
    canvas.rect(0, 0, 612, 792, stroke=0, fill=1)
    if doc.page > 1:
        canvas.setFillColor(NAVY)
        canvas.setFont(BOLD, 9)
        canvas.drawString(48, 757, "RAGTrust")
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT, 8.5)
        canvas.drawRightString(564, 757, "PUBLIC DEMO USER MANUAL")
    canvas.setStrokeColor(LINE)
    canvas.line(48, 41, 564, 41)
    canvas.setFont(FONT, 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(48, 26, "Version 0.1 | October 8, 2026 | Public demo edition")
    canvas.drawRightString(564, 26, str(doc.page))
    canvas.restoreState()


story = []


def section(number, title, intro):
    story.extend([PageBreak(), p(f"{number:02d} / USER GUIDE", "eyebrow"), p(title, "title"), p(intro)])


# 1. Cover
story.extend([Spacer(1, 16), p("RAGTRUST / PUBLIC DEMO EDITION", "eyebrow"),
              p("User manual", "title"),
              p("From trusted examples to a released benchmark.<br/>Then compare the answers returned by your RAG system.")])
story.append(Spacer(1, 16))
hero = ROOT / "docs/assets/ragtrust-linkedin.png"
story.append(Image(str(hero), width=WIDTH, height=WIDTH * 907 / 1733))
story.extend([Spacer(1, 25), p("Start here", "heading"),
    p(f'<a href="{SITE}" color="#145A82">{SITE}</a>', "small"),
    p(f'<a href="{REPO}" color="#145A82">{REPO}</a>', "small")])
cover_links = Table([[qr(SITE), p("<b>No account or password required.</b><br/>Scan to open the demo, or use the clickable link above. This guide covers the public Streamlit interface.")]], colWidths=[92, 424])
cover_links.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
story.append(cover_links)
story.append(note("Know the mode", "Public planning, generation and verification use deterministic fixture rules. RAG comparisons can use your recorded answers or a compatible public HTTPS endpoint. The public demo does not call Microsoft Foundry."))

# 2. Quick start and navigation
section(1, "Your first benchmark", "Use the included IT-security example before importing your own data. Keep the default small run for your first visit.")
story.append(Workflow())
for number, title, text in [
    (1, "Load the sample", "In the sidebar, select <b>Load IT Security Demo Data</b>. The sample contains 30 golden examples, two sources and 12 evidence segments."),
    (2, "Generate and monitor", "Open <b>3. Run &amp; Monitor</b>. Keep 4 candidates, 2 accepted, 1 repair and budget 20. Select <b>Start Generation &amp; Verification Run</b>, then <b>Refresh run progress</b>."),
    (3, "Review and release", "Inspect cases in <b>4. Case Inspector</b>. In <b>7. Export &amp; Release</b>, choose a completed run and select <b>Freeze &amp; Release Dataset Version</b>. Download your dataset."),
    (4, "Test your RAG", "Open <b>8. RAG Target Test</b>. Choose the released version. Use recorded answers (page 6) or a public HTTPS endpoint (page 7)."),
]:
    story.append(step(number, title, text))
story.append(heading("Where to find each task"))
story.append(table(["Tab", "Use it to"], [
    ("1. Project &amp; Ingest", "Create a project; import golden examples and source evidence."),
    ("2. Profile &amp; Plan", "Inspect topic quotas and coverage gaps before generation."),
    ("3. Run &amp; Monitor", "Set targets, start a run, refresh progress or cancel work."),
    ("4. Case Inspector", "Read evidence and assessments; approve, reject or correct."),
    ("5. Dataset Quality", "Inspect coverage, duplicates and evidence-support estimates."),
    ("6. Validate Evaluator", "Run the included labelled calibration benchmark."),
    ("7. Export &amp; Release", "Freeze a version and download its dataset and reports."),
    ("8. RAG Target Test", "Capture and compare endpoint or recorded responses."),
], [158, 358]))

# 3. Import
section(2, "Bring your own examples", "Bring trusted questions and answers, plus readable source evidence.")
story.append(step(1, "Create a project", "In <b>1. Project &amp; Ingest</b>, enter <b>Project Name</b>, <b>Domain</b> and optional purpose. Select <b>Create Project</b>, then choose it in the sidebar."))
story.append(step(2, "Prepare a golden file", "Use UTF-8 CSV, JSONL or a JSON array. Required: <b>question</b> and <b>answer</b>. Optional: <b>id</b>, <b>topic</b>, <b>evidence_ref</b>. Rows missing a question or answer are skipped."))
story.append(heading("CSV example"))
story.append(code('id,question,answer,topic\ng1,How long are logs kept?,365 days,retention\ng2,Is MFA required?,Yes for remote access,access'))
story.append(heading("JSONL example - one object per line"))
story.append(code('{"id":"g1","question":"How long are logs kept?","answer":"365 days","topic":"retention"}'))
story.append(p("The public uploader expects <b>answer</b>, not <b>trusted_answer</b>. The example values are sample data; replace them with answers you have verified.", "small"))
story.append(step(3, "Import and register", "Use <b>Upload Golden Examples (CSV / JSONL)</b>, check the parsed count, then <b>Import Golden Examples</b>. Upload source material, check its extracted segments, then <b>Register Source Material</b>."))
story.append(table(["Source input", "What the demo can read"], [
    ("TXT", "Separate paragraphs with blank lines. The first paragraph locator is filename.txt:sec1; match any evidence_ref to its locator."),
    ("PDF", "Extractable text; scanned PDFs are marked as requiring OCR."),
    ("JSON / VTT", "JSON uses a segments or transcript array with start, end and text. Times are seconds; end must exceed start. VTT uses timestamped cues."),
], [104, 412]))
story.append(note("Use demonstration data", "Maximum 5 MB per file; use public or non-confidential inputs. Raw images, audio and video are unsupported. Transcript text does not prove visual claims. OCR is detected but not performed."))

# 4. Generate and review
section(3, "Generate, inspect, review", "The public engine uses fixture templates and deterministic checks. These templates fit the IT-security sample better than arbitrary domains. Results exercise the workflow; they do not establish general answer accuracy.")
story.append(heading("Configure a small run"))
story.append(table(["Control", "How to use it"], [
    ("Candidate target", "How many candidate cases to request; maximum 20 in the public demo."),
    ("Accepted target", "Desired accepted count; cannot exceed the candidate target."),
    ("Repair limit per case", "Maximum repair attempts; public limit is 1."),
    ("Candidate budget units", "Two units per generated candidate. These are volume units, not money or provider tokens."),
    ("Optional topic quotas", "A JSON object whose nonnegative values total the candidate target. Leave {} for the default plan."),
], [150, 366]))
story.append(p("<b>2. Profile &amp; Plan</b> lets you run the planning agent and inspect quotas or gaps. Planning controls are separate from the generation form: enter any approved quotas in the generation form when needed."))
story.append(p("Select <b>Start Generation &amp; Verification Run</b>, then <b>Refresh run progress</b>. Wait for completion before starting another public run. Cancellation takes effect after the current operation finishes."))
story.append(heading("Read the case status"))
story.append(table(["Status", "Meaning and next step"], [
    ("accepted", "Passed the configured checks or was approved by a reviewer. Still inspect the evidence."),
    ("needs_revision", "A repair may be needed. Review the latest attempt and its failed checks."),
    ("needs_review", "Human judgment is needed before acceptance."),
    ("rejected", "Failed checks. Inspect the reason; do not include it without a justified review."),
], [105, 411]))
story.append(p("In <b>4. Case Inspector</b>, read the question, reference answer, evidence references and assessments. Use <b>Approve</b>, <b>Reject</b> or enter a <b>Correct Answer</b> and select <b>Submit Correction</b>. Review the latest repair attempt. Corrections approve the case but clear stale scores to <b>Not assessed</b>."))
story.append(p("<b>6. Validate Evaluator</b> tests the checker against the included labelled benchmark. Its accuracy and confusion matrix describe that benchmark, not the accuracy of your RAG system.", "small"))

# 5. Exports
section(4, "Freeze and download", "A release freezes an approved dataset snapshot. RAG comparisons use that snapshot, rather than answers changed later in the inspector.")
story.append(step(1, "Choose a completed run", "Open <b>7. Export &amp; Release</b>. Select the run under <b>Select Completed Run</b>. Runs marked completed or completed with a shortfall can be selected; check the accepted count first."))
story.append(step(2, "Freeze the version", "Select <b>Freeze &amp; Release Dataset Version</b>. Expand the version under <b>Published Releases &amp; Artifacts</b>. Confirm its accepted-case count."))
story.append(step(3, "Download what you need", "Download your artifacts before leaving the session. Freezing a version does not make the temporary workspace a durable storage service."))
story.append(table(["Download", "Use"], [
    ("JSONL dataset", "Canonical released cases for scripts and evaluation tools."),
    ("CSV dataset", "Flattened dataset for spreadsheets and manual inspection."),
    ("Quality Report (HTML)", "Readable dataset checks and disclosed limitations."),
    ("All case assessments", "Case-level checks and assessment records in JSONL."),
    ("Machine-readable summary", "Summary and metrics as JSON."),
], [174, 342]))
story.append(heading("Recognize the export panel"))
shot = ROOT / "docs/assets/ragtrust-exports.jpg"
if shot.exists():
    image = Image(str(shot), width=150, height=150 * 853 / 634)
    explanation = p("<b>Example from the public fixture demo</b><br/><br/>The version panel shows the accepted count, file hashes and download buttons. The hashes identify the exported file contents.<br/><br/>Download controls can stack vertically on a narrow screen. Scroll down to find assessments and the JSON summary.<br/><br/>A later correction does not rewrite an existing frozen version. Review and create a new release when you need an updated snapshot.")
    pair = Table([[image, explanation]], colWidths=[170, 346])
    pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(pair)

# 6. Recorded comparisons
section(5, "Compare recorded answers", "Choose this method when your RAG runs locally, is private, or requires authentication. Use non-confidential sample questions and responses on the public demo.")
for number, title, text in [
    (1, "Run the released questions through your RAG", "Download the dataset from page 5. Keep each question's wording exactly as released, and capture the string answer returned by your system."),
    (2, "Open the comparison screen", "In <b>8. RAG Target Test</b>, choose <b>Select Approved Dataset Version</b>. Clear <b>RAG Endpoint URL (Optional)</b>. Leave <b>Use clearly labelled fixture responses (demonstration only)</b> unchecked."),
    (3, "Paste or upload a response mapping", "Paste JSON into <b>Or recorded responses as a JSON question-to-answer mapping</b>, or use <b>Upload recorded responses (JSON question-to-answer mapping)</b>. An uploaded file takes precedence over pasted text."),
]:
    story.append(step(number, title, text))
story.append(code('{\n  "Exact question copied from the released dataset":\n    "The answer returned by your RAG system"\n}'))
story.append(p("Replace the example key with the <b>exact released question</b>. Each value must be a string. Supply an entry for <b>every released question</b>; the adapter evaluates the entire release and counts missing entries as errors."))
story.append(step(4, "Run and inspect", "Select <b>Run RAG Endpoint Evaluation</b>. Check that the mode is <b>recorded</b>, inspect the error count, and compare each captured answer with its reference and limitations."))
story.append(note("Avoid a misleading comparison", "The fixture-response checkbox copies reference answers only to demonstrate the screen. Keep it off when testing your own answers. Recorded-mode latency measures the local comparison step, not your RAG's original serving time."))
story.append(heading("What to look for"))
story.append(p("A response can be captured successfully yet be wrong or incomplete. Read the answer and source context yourself. Lexical overlap is a useful surface comparison, not a factual-accuracy or faithfulness score."))

# 7. Endpoint comparisons
section(6, "Connect a public endpoint", "The adapter sends each released question to an endpoint you control. Reference answers and source documents are not sent in the request.")
story.append(heading("Required request and response"))
story.append(p("Your endpoint must accept an HTTPS JSON POST on port 443. Example request:"))
story.append(code('{"query": "The released evaluation question"}'))
story.append(p("Return a JSON object with a string <b>answer</b> or <b>response</b>:"))
story.append(code('{"answer": "Your RAG system answer"}'))
story.append(p('Alternative response: <font name="Courier">{&quot;response&quot;: &quot;Your RAG system answer&quot;}</font>', "small"))
story.append(table(["Requirement", "Supported contract"], [
    ("Network", "Public HTTPS on port 443; private, local and loopback destinations are rejected."),
    ("Authentication", "No API-key or custom-header field. Use recorded answers for an authenticated or private service."),
    ("Redirects / proxies", "Redirects are not followed; environment proxies are disabled."),
    ("Response", "Uncompressed JSON, at most 1 MiB. Network operations have timeouts and a 15-second response limit."),
    ("Dataset size", "At most 20 released cases per public comparison."),
], [140, 376]))
story.append(step(1, "Select a release and enter your URL", "Choose <b>Select Approved Dataset Version</b>, then enter your compatible URL in <b>RAG Endpoint URL (Optional)</b>. Avoid embedded credentials. Keep the fixture-response checkbox unchecked."))
story.append(step(2, "Evaluate and read failures", "Select <b>Run RAG Endpoint Evaluation</b>. The mode should be <b>live_endpoint</b>. Inspect answer capture, latency and errors. A timeout or invalid response is a failed response, not a zero-quality answer."))
story.append(note("If your service has a different contract", "Adapt your own endpoint to this request/response format, or run the questions independently and upload recorded answers. The demo does not connect to localhost or services on your private network."))

# 8. Interpretation and support
section(7, "Read your results", "Dataset checks and RAG-response comparisons answer different questions. Neither should be read as independent proof that a RAG system is accurate.")
story.append(table(["Signal", "What it means"], [
    ("Dataset checks", "Coverage, duplicates, citations and automated evidence support describe the dataset being built."),
    ("Reference token recall", "Word overlap with the reference. A wrong answer can overlap; a correct paraphrase can score poorly."),
    ("Abstention phrase match", "A phrase heuristic for cases expected to abstain, not a complete understanding of refusal quality."),
    ("Latency / errors", "Endpoint timing and capture failures. Recorded and fixture modes do not benchmark serving latency."),
    ("Semantic quality", "Shown as Not assessed. The adapter does not establish accuracy, faithfulness or retrieval quality."),
], [140, 376]))
story.append(heading("Review a comparison in this order"))
story.append(step(1, "Confirm the mode and captured count", "Use <b>recorded</b> for your uploaded answers or <b>live_endpoint</b> for endpoint calls. Confirm all released questions have responses, then investigate errors before comparing scores."))
story.append(step(2, "Read answers against their evidence", "Inspect the question, your RAG's answer, the reference and its original source. Look for unsupported claims, omitted conditions, wrong numbers and appropriate abstention. A high overlap score alone cannot resolve these issues."))
story.append(step(3, "Make a representative human review", "Check examples from each topic, including failures and surprising scores. Record your judgments independently. Use the findings to improve source coverage, retrieval or answer generation, then repeat with the same release for comparison."))
story.append(note("Keep the benchmark stable", "Use the same frozen version when comparing configurations. If you correct reference answers, create a new release and label subsequent comparisons with that version. Results from different datasets are not directly comparable."))

# 9. Troubleshooting and support
section(8, "Troubleshooting and support", "Each visitor has a separate temporary workspace. Download your datasets and reports before leaving, resetting, or sharing a result.")
story.append(table(["What you see", "What to do"], [
    ("Site is slow or unavailable", "The free Azure host may cold-start or reach its allowance. Try again later; keep local exports."),
    ("No project / no release", "Load the sample or create a project. Complete generation and freeze a version before comparing RAG answers."),
    ("Zero parsed examples / OCR needed", "Use exact question and answer fields. Supply readable PDF text or an OCR-produced text file; the demo does not run OCR."),
    ("Run fails or ends with shortfall", "Check imported seeds, candidate/accepted targets and quota totals. Inspect failed checks; a requested accepted count is not guaranteed."),
    ("Missing or invalid recorded answers", "Use valid JSON with exact question keys and string values. Clear the endpoint and keep fixture mode unchecked."),
    ("Endpoint cannot be evaluated", "Check public HTTPS:443, JSON format, response size/encoding, timeout and redirects. Use recorded mode for private/authenticated services."),
], [151, 365]))
story.append(note("Keep your work", "Public limits: 20 candidates per run, 1 repair per case and 5 MB per upload. Workspaces reset on the next interaction after two hours; disconnected sessions have a 120-second reconnect window. Use Reset my workspace only after downloading what you want to keep."))
story.append(p(f'<b>Help and feedback:</b> <a href="{REPO}/issues" color="#145A82">{REPO}/issues</a><br/>Share the steps, error message and a small non-confidential example. Include no credentials or private records.', "small"))


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=(612, 792), leftMargin=48, rightMargin=48,
                            topMargin=57, bottomMargin=54, title="RAGTrust User Manual",
                            author="Nithin9Krishna", subject="Public demo quick start and RAG testing guide")
    doc.build(story, onFirstPage=page, onLaterPages=page)
    print(OUT)


if __name__ == "__main__":
    main()
