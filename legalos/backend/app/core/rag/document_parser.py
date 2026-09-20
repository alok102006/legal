import io
import csv
import fitz  # PyMuPDF
import docx
from app.shared.exceptions import BadRequestException


def parse_pdf(file_bytes: bytes) -> str:
    """Extracts text from PDF bytes using PyMuPDF (fitz)."""
    text_content = []
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page_num, page in enumerate(doc, 1):
                page_text = page.get_text().strip()
                if page_text:
                    text_content.append(f"--- Page {page_num} ---\n{page_text}")
        return "\n\n".join(text_content)
    except Exception as e:
        raise BadRequestException(f"Failed to parse PDF document: {str(e)}")


def parse_docx(file_bytes: bytes) -> str:
    """Extracts text from DOCX bytes using python-docx."""
    text_content = []
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        for para in doc.paragraphs:
            if para.text.strip():
                text_content.append(para.text.strip())
        
        # Also extract text from tables if present
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_text:
                    text_content.append(row_text)
                    
        return "\n".join(text_content)
    except Exception as e:
        raise BadRequestException(f"Failed to parse DOCX document: {str(e)}")


def parse_csv(file_bytes: bytes) -> str:
    """Extracts text from CSV file bytes."""
    try:
        content_str = file_bytes.decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(content_str))
        lines = []
        headers = []
        for idx, row in enumerate(reader):
            if not row:
                continue
            if idx == 0:
                headers = row
                lines.append("Headers: " + " | ".join(row))
            else:
                row_str = ", ".join([f"{headers[i] if i < len(headers) else f'Col_{i}'}: {val.strip()}" for i, val in enumerate(row) if val.strip()])
                if row_str:
                    lines.append(f"Row {idx}: {row_str}")
        return "\n".join(lines)
    except Exception as e:
        raise BadRequestException(f"Failed to parse CSV document: {str(e)}")


def parse_excel(file_bytes: bytes) -> str:
    """Extracts text from Excel (.xlsx/.xls) file bytes using openpyxl or fallback."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheets_text = []
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            sheet_lines = [f"=== Sheet: {sheet_name} ==="]
            for row in sheet.iter_rows(values_only=True):
                row_vals = [str(val).strip() for val in row if val is not None and str(val).strip() != ""]
                if row_vals:
                    sheet_lines.append(" | ".join(row_vals))
            if len(sheet_lines) > 1:
                sheets_text.append("\n".join(sheet_lines))
        return "\n\n".join(sheets_text)
    except Exception as e:
        # Fallback text decoding if openpyxl fails
        try:
            return file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            raise BadRequestException(f"Failed to parse Excel document: {str(e)}")


def parse_txt(file_bytes: bytes) -> str:
    """Extracts text from plain text file bytes."""
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        raise BadRequestException(f"Failed to parse TXT document: {str(e)}")


def parse_document(file_bytes: bytes, filename: str) -> str:
    """
    Central document parser supporting PDF, DOCX, CSV, EXCEL, TXT, and MD files.
    """
    ext = filename.lower().split(".")[-1]
    if ext == "pdf":
        return parse_pdf(file_bytes)
    elif ext in ["docx", "doc"]:
        return parse_docx(file_bytes)
    elif ext == "csv":
        return parse_csv(file_bytes)
    elif ext in ["xlsx", "xls"]:
        return parse_excel(file_bytes)
    elif ext in ["txt", "md"]:
        return parse_txt(file_bytes)
    else:
        raise BadRequestException(f"Unsupported file type: .{ext}. Supported formats are PDF, DOCX, CSV, EXCEL, TXT, MD.")
