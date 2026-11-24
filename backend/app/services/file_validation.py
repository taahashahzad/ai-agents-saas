"""Upload validation: filename, extension, MIME type, size and real file content.

Nothing here trusts the client: the stored name is sanitized, the type comes from the
extension AND must agree with the declared MIME type AND with the file's actual bytes.
"""
import codecs
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from typing import BinaryIO

from app.core.errors import PayloadTooLargeError, UnprocessableFileError, UnsupportedMediaTypeError
from app.schemas.document import DocumentType

ALLOWED_MIME_TYPES: dict[DocumentType, frozenset[str]] = {
    DocumentType.pdf: frozenset({"application/pdf"}),
    DocumentType.docx: frozenset({
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
    DocumentType.txt: frozenset({"text/plain"}),
    # Windows browsers often label .csv files application/vnd.ms-excel.
    DocumentType.csv: frozenset({"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"}),
}

# What the download endpoint sends. Never echoes the client-declared value.
CANONICAL_MIME: dict[DocumentType, str] = {
    DocumentType.pdf: "application/pdf",
    DocumentType.docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    DocumentType.txt: "text/plain; charset=utf-8",
    DocumentType.csv: "text/csv; charset=utf-8",
}

MAX_DOCX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # zip-bomb guard
MAX_DOCX_ENTRIES = 5000
_MAX_STEM = 100


@dataclass(frozen=True)
class CleanName:
    original: str   # what the user called it (path stripped, control chars removed)
    safe: str       # filesystem/URL-safe version
    file_type: DocumentType


def sanitize_filename(raw: str | None) -> CleanName:
    if not raw or not raw.strip():
        raise UnsupportedMediaTypeError("A file with a name is required.")
    name = raw.replace("\\", "/").split("/")[-1]                      # drop any path
    name = unicodedata.normalize("NFC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip().rstrip(".")
    stem, dot, ext = name.rpartition(".")
    ext = ext.lower()
    if not dot or not stem.strip():
        raise UnsupportedMediaTypeError("The file must have a name and an extension (.pdf, .docx, .txt, .csv).")
    try:
        file_type = DocumentType(ext)
    except ValueError:
        raise UnsupportedMediaTypeError("Unsupported file type. Allowed: PDF, DOCX, TXT, CSV.")
    safe_stem = re.sub(r"[^\w \-()]", "_", stem)                       # letters/digits/_/space/-/()
    safe_stem = re.sub(r"[ _]{2,}", "_", safe_stem).strip(" _")[:_MAX_STEM] or "document"
    return CleanName(original=name[:255], safe=f"{safe_stem}.{ext}", file_type=file_type)


def check_mime_type(file_type: DocumentType, declared: str | None) -> str:
    mime = (declared or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME_TYPES[file_type]:
        raise UnsupportedMediaTypeError("The file's MIME type does not match its extension.")
    return mime


def read_limited(stream: BinaryIO, max_bytes: int) -> bytes:
    """Read at most max_bytes; refuse (413) as soon as the file is bigger."""
    chunks, total = [], 0
    while True:
        chunk = stream.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                f"The file exceeds the maximum size of {max_bytes / (1024 * 1024):g} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


def decode_text(data: bytes) -> str:
    """Decode user text files: UTF-8 (with/without BOM), UTF-16 with BOM, then Windows-1252."""
    if data.startswith(codecs.BOM_UTF8):
        return data.decode("utf-8-sig")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")  # raises UnicodeDecodeError if still undecodable


def validate_content(file_type: DocumentType, data: bytes) -> None:
    """Check the bytes really look like the declared type. Raises 422 invalid_file."""
    if not data:
        raise UnprocessableFileError("The file is empty.")
    if file_type is DocumentType.pdf:
        if b"%PDF-" not in data[:1024]:
            raise UnprocessableFileError("The file is not a valid PDF.")
    elif file_type is DocumentType.docx:
        _validate_docx(data)
    else:  # txt / csv
        has_bom = data.startswith((codecs.BOM_UTF8, codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE))
        if not has_bom and b"\x00" in data[:8192]:
            raise UnprocessableFileError("The file looks like a binary file, not text.")
        try:
            decode_text(data)
        except (UnicodeDecodeError, UnicodeError):
            raise UnprocessableFileError("The file's text encoding is not supported.")


def _validate_docx(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            names = {i.filename for i in infos}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise UnprocessableFileError("The file is not a valid DOCX document.")
            if len(infos) > MAX_DOCX_ENTRIES or sum(i.file_size for i in infos) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise UnprocessableFileError("The DOCX document is too large to process safely.")
    except zipfile.BadZipFile:
        raise UnprocessableFileError("The file is not a valid DOCX document.")
