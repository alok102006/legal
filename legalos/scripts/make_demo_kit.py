"""Build the three demo PDFs in docs/demo_kit from the demo texts, with letterheads, references, page numbers
and signature blocks so they read as real paper. Run on the host: python scripts/make_demo_kit.py"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "demo"
OUT = ROOT / "docs" / "demo_kit"
OUT.mkdir(exist_ok=True)

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["Normal"], fontName="Times-Roman", fontSize=10.5, leading=15, spaceAfter=6)
HEAD = ParagraphStyle("head", parent=BODY, fontName="Times-Bold", fontSize=11, spaceBefore=10, spaceAfter=4)
TITLE = ParagraphStyle("title", parent=BODY, fontName="Times-Bold", fontSize=15, alignment=1, spaceAfter=14, leading=19)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.5, leading=11, textColor=colors.HexColor("#444444"))


def letterhead(name: str, line2: str, right: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 12); canvas.drawString(20 * mm, 282 * mm, name)
        canvas.setFont("Helvetica", 8); canvas.drawString(20 * mm, 277 * mm, line2)
        canvas.drawRightString(190 * mm, 282 * mm, right)
        canvas.setStrokeColor(colors.HexColor("#999999")); canvas.line(20 * mm, 273 * mm, 190 * mm, 273 * mm)
        canvas.setFont("Helvetica", 8); canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def paragraphs(text: str):
    out = []
    for block in text.split("\n"):
        b = block.strip()
        if not b:
            out.append(Spacer(1, 3)); continue
        esc = b.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        is_head = (b.isupper() and len(b) < 70) or (b[:2].rstrip(".").isdigit() and b[:3].count(".") == 1 and b.split(" ", 1)[0].rstrip(".").isdigit() and b.upper() == b)
        out.append(Paragraph(esc, HEAD if is_head else BODY))
    return out


def build(src: str, dest: str, title: str, lh: tuple, signatures: list, ref: str):
    text = (SRC / src).read_text(encoding="utf-8")
    doc = SimpleDocTemplate(str(OUT / dest), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=32 * mm, bottomMargin=20 * mm,
                            title=title, author=lh[0])
    story = [Paragraph(ref, SMALL), Spacer(1, 6), Paragraph(title, TITLE)]
    story += paragraphs(text)
    story.append(Spacer(1, 18))
    rows = [[Paragraph(f"<b>{a}</b><br/>{b}", SMALL) for a, b in signatures]]
    t = Table(rows, colWidths=[80 * mm] * len(rows[0]))
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 8)]))
    story.append(t)
    doc.build(story, onFirstPage=letterhead(*lh), onLaterPages=letterhead(*lh))
    print("wrote", OUT / dest)


build("01_yarn_supply_agreement.txt", "01_Yarn_Supply_Agreement_Patel_Yarn_Traders.pdf", "YARN SUPPLY AGREEMENT",
      ("PATEL YARN TRADERS", "Ring Road, Surat, Gujarat 395002  |  GSTIN 24AAFFP7890L1ZN", "Agreement No. PYT/KT/2026/04"),
      [("For PATEL YARN TRADERS", "Partner<br/>Date: 01 April 2026"), ("For KULKARNI TEXTILES PVT LTD", "Director<br/>Date: 01 April 2026")],
      "Stamp paper Rs 300 | Executed at Surat")
build("02_cheque_bounce_notice.txt", "02_Legal_Notice_Mehta_Associates.pdf", "LEGAL NOTICE",
      ("MEHTA & ASSOCIATES", "Advocates & Solicitors  |  204, Nanpura, Surat 395001  |  Reg. No. G/1234/2008", "By Speed Post AD and Email"),
      [("MEHTA & ASSOCIATES", "Advocate for Patel Yarn Traders<br/>Enrolment No. G/1234/2008")],
      "Ref: MA/2026/118  |  Date: 12 October 2026")
build("03_employee_handbook.txt", "03_Employee_Handbook_Kulkarni_Textiles.pdf", "EMPLOYEE HANDBOOK",
      ("KULKARNI TEXTILES PRIVATE LIMITED", "Plot 14, Sachin GIDC, Surat, Gujarat 394230  |  CIN U17110GJ2013PTC074512", "HR-POL-001 | Version 3.1 | Effective 01 April 2026"),
      [("Approved by", "Ramesh Kulkarni, Managing Director<br/>Date: 25 March 2026"), ("Issued by", "Human Resources<br/>Kulkarni Textiles Pvt Ltd")],
      "Document HR-POL-001  |  Version 3.1")
