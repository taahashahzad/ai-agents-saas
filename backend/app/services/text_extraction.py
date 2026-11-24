"""Pure text extraction: bytes in -> clean text out. No Firestore, no Storage, no HTTP.

That keeps it trivially reusable from a future background worker. Failures raise
ExtractionError carrying a message that is safe to show to end users (never raw
exception text from third-party libraries).
"""
import csv
import io
import logging
import re
import unicodedata

from app.schemas.document import DocumentType
from app.services.file_validation import decode_text

logger = logging.getLogger(__name__)

MAX_EXTRACTED_CHARS = 5_000_000


class ExtractionError(Exception):
    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)


def normalize_text(text: str) -> str:
    """Clean whitespace/control characters without changing the words or their order."""
    text = unicodedata.normalize("NFC", text).translate(_ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n\n")
    text = "".join(ch for ch in text
                   if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    lines = []
    for line in text.split("\n"):
        line = "".join(" " if unicodedata.category(ch) == "Zs" or ch == "\t" else ch for ch in line)
        lines.append(re.sub(r" {2,}", " ", line).strip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _check_size(total: int) -> None:
    if total > MAX_EXTRACTED_CHARS:
        raise ExtractionError("The document contains too much text to process.")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("The PDF is password-protected. Remove the password and upload it again.")
        parts, total = [], 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            total += len(page_text)
            _check_size(total)
            parts.append(page_text)
    except ExtractionError:
        raise
    except Exception as exc:
        logger.warning("PDF extraction failed (%s)", type(exc).__name__)
        raise ExtractionError("The PDF could not be read. It may be corrupted.")
    text = "\n\n".join(parts)
    if not text.strip():
        raise ExtractionError(
            "No text could be extracted. Scanned or image-only PDFs are not supported yet.")
    return text


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        document = Document(io.BytesIO(data))
        blocks, total = [], 0
        for child in document.element.body.iterchildren():  # keeps paragraphs/tables in order
            if child.tag.endswith("}p"):
                text = Paragraph(child, document).text
            elif child.tag.endswith("}tbl"):
                rows = []
                for row in Table(child, document).rows:
                    cells = []
                    for cell in row.cells:
                        value = cell.text.strip().replace("\n", " ")
                        if not cells or cells[-1] != value:  # merged cells repeat their text
                            cells.append(value)
                    rows.append(" | ".join(cells))
                text = "\n".join(rows)
            else:
                continue
            total += len(text)
            _check_size(total)
            blocks.append(text)
    except ExtractionError:
        raise
    except Exception as exc:
        logger.warning("DOCX extraction failed (%s)", type(exc).__name__)
        raise ExtractionError("The DOCX document could not be read. It may be corrupted.")
    return "\n".join(blocks)


def _extract_txt(data: bytes) -> str:
    try:
        return decode_text(data)
    except UnicodeError:
        raise ExtractionError("The file's text encoding is not supported.")


def _extract_csv(data: bytes) -> str:
    """First row = column names. Each later row becomes "column: value | column: value"
    so every value keeps its meaning once the text is split into chunks (RAG, Phase 4)."""
    try:
        text = decode_text(data)
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = [r for r in csv.reader(io.StringIO(text, newline=""), dialect) if any(c.strip() for c in r)]
    except UnicodeError:
        raise ExtractionError("The file's text encoding is not supported.")
    except csv.Error:
        raise ExtractionError("The CSV file could not be parsed.")
    if not rows:
        return ""
    header = [(h.strip() or f"column_{i + 1}") for i, h in enumerate(rows[0])]
    lines, total = ["Columns: " + " | ".join(header)], 0
    for row in rows[1:]:
        cells = [f"{header[i] if i < len(header) else f'column_{i + 1}'}: {v.strip()}"
                 for i, v in enumerate(row) if v.strip()]
        if cells:
            line = " | ".join(cells)
            total += len(line)
            _check_size(total)
            lines.append(line)
    return "\n".join(lines)


_EXTRACTORS = {
    DocumentType.pdf: _extract_pdf,
    DocumentType.docx: _extract_docx,
    DocumentType.txt: _extract_txt,
    DocumentType.csv: _extract_csv,
}


def extract_text(file_type: DocumentType, data: bytes) -> str:
    """Extract + normalize. Raises ExtractionError (user-safe message) on any failure."""
    text = normalize_text(_EXTRACTORS[file_type](data))
    if not text:
        raise ExtractionError("The document contains no readable text.")
    _check_size(len(text))
    return text
