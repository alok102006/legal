import io

import pytest

from app.core.rag import parsing
from app.shared.exceptions import BadRequestException
from app.workspaces.contract_intelligence.engine.segmenter import segment_contract
from tests.workspaces.contract_intelligence.sample_contracts import SUPPLY_AGREEMENT


def _text_pdf(pages):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for page_lines in pages:
        y = 800
        for line in page_lines:
            c.drawString(40, y, line[:110])
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


def _image_only_pdf():
    from PIL import Image, ImageDraw
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    img = Image.new("RGB", (600, 800), "white")
    ImageDraw.Draw(img).text((40, 40), "scanned page", fill="black")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(img), 0, 0, width=595, height=842)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_text_pdf_is_parsed_with_page_numbers():
    lines = [l for l in SUPPLY_AGREEMENT.splitlines() if l.strip()]
    half = len(lines) // 2
    pdf = _text_pdf([lines[:half], lines[half:]])
    doc = parsing.parse_contract_file(pdf, "agreement.pdf")
    assert doc.kind == "pdf" and doc.has_pages and not doc.is_scanned
    assert [p.number for p in doc.pages] == [1, 2]
    segs = segment_contract(doc)
    assert any(s.page_start == 2 for s in segs) and any(s.page_start == 1 for s in segs)


def test_scanned_pdf_is_flagged():
    doc = parsing.parse_contract_file(_image_only_pdf(), "scan.pdf")
    assert doc.is_scanned and any("scanned" in w.lower() for w in doc.warnings)


def test_corrupt_pdf_gives_friendly_error():
    with pytest.raises(BadRequestException):
        parsing.parse_contract_file(b"%PDF-1.4 definitely not a pdf", "bad.pdf")


def test_docx_roundtrip_keeps_order_and_tables():
    import docx

    d = docx.Document()
    d.add_paragraph("1. PAYMENT")
    d.add_paragraph("Pay within 30 days.")
    t = d.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text = "Item"
    t.rows[0].cells[1].text = "Rs. 5,00,000"
    d.add_paragraph("2. TERM")
    buf = io.BytesIO()
    d.save(buf)
    doc = parsing.parse_contract_file(buf.getvalue(), "a.docx")
    text = doc.text
    assert text.index("PAYMENT") < text.index("Rs. 5,00,000") < text.index("TERM")
    assert not doc.has_pages


def test_text_encoding_fallback():
    doc = parsing.parse_contract_file("Rs. ₹5,00,000 – payable".encode("cp1252", errors="ignore"), "a.txt")
    assert "payable" in doc.text


def test_unsupported_extension():
    with pytest.raises(BadRequestException):
        parsing.parse_contract_file(b"x", "a.exe")
