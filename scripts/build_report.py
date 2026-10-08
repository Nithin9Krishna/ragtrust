"""Render the checked implementation report and vector architecture diagram."""
from pathlib import Path
from html import escape
import re

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/RAGTrust_Final_Report.pdf"
NAVY = colors.HexColor("#15344B")
TEAL = colors.HexColor("#007C83")
GREY = colors.HexColor("#536475")


def architecture():
    drawing = Drawing(492, 315)
    def box(x, y, w, h, lines, fill="#EAF4F6"):
        drawing.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=colors.HexColor(fill), strokeColor=TEAL, strokeWidth=0.8))
        for i, line in enumerate(lines):
            drawing.add(String(x+w/2, y+h/2+(len(lines)-1)*6-i*12, line, textAnchor="middle", fontName="Helvetica", fontSize=9, fillColor=NAVY))
    def arrow(x, y, xx, yy):
        drawing.add(Line(x,y,xx,yy,strokeColor=GREY,strokeWidth=1))
        if yy < y:
            p = [xx-3, yy+5, xx+3, yy+5, xx, yy]
        elif xx > x:
            p = [xx-5,yy-3,xx-5,yy+3,xx,yy]
        else:
            p = [xx+5,yy-3,xx+5,yy+3,xx,yy]
        drawing.add(Polygon(p, fillColor=GREY,strokeColor=GREY))
    box(154,268,184,38,["Golden examples + source evidence"])
    box(154,211,184,39,["Private Streamlit workspace", "Python orchestrator / FastAPI"])
    arrow(246,268,246,250)
    box(2,139,110,46,["1. Understand", "and plan"])
    box(127,139,110,46,["2. Generate", "provisional cases"])
    box(252,139,110,46,["3. Verify", "claims independently"])
    box(377,139,110,46,["4. Refine", "bounded repair"])
    arrow(246,211,246,198)
    drawing.add(Line(57,198,432,198,strokeColor=GREY))
    for x in [57,182,307,432]: arrow(x,198,x,185)
    drawing.add(String(246,122,"Four named, versioned Microsoft Foundry prompt agents",textAnchor="middle",fontSize=9,fillColor=TEAL))
    box(154,61,184,43,["Deterministic checks + human review", "Persist attempts and metric results"],"#F2F4F8")
    arrow(307,139,307,128)
    drawing.add(Line(307,113,307,105,strokeColor=GREY))
    box(2,2,143,39,["SQLite + source storage", "Project records and evidence"],"#F2F4F8")
    box(175,2,143,39,["Immutable dataset release", "JSONL / CSV / HTML / JSON"],"#F2F4F8")
    box(349,2,138,39,["Optional RAG comparison", "Recorded or live responses"],"#F2F4F8")
    arrow(246,61,246,41)
    arrow(175,22,145,22)
    arrow(318,22,349,22)
    drawing.scale(0.87, 0.87)
    drawing.width *= 0.87
    drawing.height *= 0.87
    return drawing


def footer(canvas, doc):
    canvas.saveState()
    width, height = doc.pagesize
    canvas.setStrokeColor(colors.HexColor("#DAE2EA"))
    canvas.line(48, 39, width-48,39)
    canvas.setFont("Helvetica",8)
    canvas.setFillColor(GREY)
    canvas.drawString(48,26,"RAGTrust | Implementation, verification and submission guide")
    canvas.drawRightString(width-48,26,str(doc.page))
    canvas.restoreState()


def main():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodyRT",fontName="Helvetica",fontSize=10,leading=14,textColor=NAVY,spaceAfter=8,allowOrphans=0,allowWidows=0))
    styles.add(ParagraphStyle(name="HeadingRT",fontName="Helvetica-Bold",fontSize=21,leading=26,textColor=NAVY,spaceAfter=16))
    styles.add(ParagraphStyle(name="SubRT",fontName="Helvetica-Bold",fontSize=12,leading=17,textColor=TEAL,spaceBefore=10,spaceAfter=6,keepWithNext=True))
    styles.add(ParagraphStyle(name="TitleRT",fontName="Helvetica-Bold",fontSize=44,leading=50,textColor=NAVY,spaceAfter=18))
    story = [Spacer(1,55), Paragraph("RAGTrust",styles["TitleRT"]),
        Paragraph("Synthetic evaluation data,<br/>with inspectable evidence",styles["HeadingRT"]),
        Spacer(1,14),Paragraph("Final implementation and demonstration report",styles["SubRT"]),
        Paragraph("Sai Nithin Krishna<br/>Microsoft Agent-a-thon Architect<br/>25 September 2026",styles["BodyRT"]),Spacer(1,25)]
    cards = Table([["4 FOUND RY AGENTS".replace("FOUND RY","FOUNDRY"),"35 TESTS PASSED","LIVE WORKFLOW VERIFIED"],["Versioned prompt roles","API and trust controls","2 generated / 2 accepted"]],colWidths=[162,162,162])
    cards.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EAF4F6")),("TEXTCOLOR",(0,0),(-1,-1),NAVY),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),9),("FONTSIZE",(0,1),(-1,1),9),("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12)]))
    story += [cards,Spacer(1,27),Paragraph("Implemented scope: the text-first generation, validation, review and export workflow. Raw-media processing and enterprise scaling remain explicit roadmap items.",styles["BodyRT"]),Spacer(1,15),Paragraph("Use this report with the source package, measured sample release and recording guide. The video and final course upload are completed by the project owner.",styles["BodyRT"])]
    text = (ROOT / "docs/FINAL_REPORT.md").read_text()
    paragraphs = re.split(r"\n\s*\n",text)
    for paragraph in paragraphs:
        if paragraph.startswith("# ") or paragraph.startswith("Prepared for"):
            continue
        if paragraph.startswith("## "):
            story += [PageBreak(),Paragraph(escape(paragraph[3:]),styles["HeadingRT"])]
            if paragraph.startswith("## 2."):
                story += [architecture(),Spacer(1,16)]
        elif paragraph.startswith("### "):
            story.append(Paragraph(escape(paragraph[4:]),styles["SubRT"]))
        else:
            story.append(Paragraph(escape(paragraph.replace("\n"," ")),styles["BodyRT"]))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    doc = SimpleDocTemplate(str(OUT),pagesize=(612,792),leftMargin=48,rightMargin=48,topMargin=47,bottomMargin=55,
        title="RAGTrust - Final Implementation and Submission Report",author="Sai Nithin Krishna")
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(OUT)


if __name__ == "__main__":
    main()
