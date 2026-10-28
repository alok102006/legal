"""Safe local storage for uploaded files.

What it guarantees (`save_file`):
- the stored name is harmless (no path tricks, no control characters; Devanagari and other scripts are kept);
- every organisation has its own folder, and an organisation can never reach another one's files;
- the size limit comes from configuration (UPLOAD_MAX_MB);
- the type is decided from the file's first bytes (magic numbers), never from the extension alone: executables
  and scripts are refused whatever they are called, and a ".pdf" that is not a PDF is refused;
- the same content uploaded twice by the same organisation is stored once: the second call returns the existing
  path. A small reference count next to the file keeps `delete_file` honest, so deleting one record never removes
  the file another record still points at.

`validate_upload` is the same check without saving, for workspaces that want to reject before doing other work.
`cleanup_orphans` removes files no record points at any more.
"""
import asyncio
import hashlib
import io
import logging
import os
import re
import threading
import time
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from typing import Iterable, Optional

import aiofiles

from app.config import settings
from app.shared.exceptions import LegalOSException

logger = logging.getLogger("legalos.storage")

# Directory for storing uploaded files locally (tests point this at a temp folder)
UPLOAD_DIR = settings.upload_dir

_REFS_SUFFIX = ".refs"
_HASH_CHARS = 16
_lock = threading.Lock()          # dedupe + refcount changes are tiny read-modify-write sequences on disk


class UploadRejected(LegalOSException):
    """Upload refused. 413 for size, 415 for type, 400 for everything else."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail=detail)


# ------------------------------------------------------------------ names

_FORBIDDEN_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def safe_filename(filename: str) -> str:
    """Keeps letters, digits and marks of any script plus `._-() `; never returns an empty, hidden or reserved name."""
    base = os.path.basename((filename or "").replace("\\", "/"))
    base = unicodedata.normalize("NFC", base)
    base = "".join(c if (unicodedata.category(c)[0] in "LMN" or c in "._-() ") else "_" for c in base)
    base = re.sub(r"_{2,}", "_", base).strip(" .") or "file"
    stem, ext = os.path.splitext(base)
    if stem.lower() in _FORBIDDEN_NAMES:
        stem = f"_{stem}"
    return (stem[: max(1, 120 - len(ext))] + ext)[:120]


def _extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower().lstrip(".")


# ------------------------------------------------------------------ type sniffing

_EXECUTABLE_EXTENSIONS = {
    "exe", "dll", "com", "scr", "msi", "bat", "cmd", "ps1", "vbs", "vbe", "js", "jse", "wsf", "hta", "jar", "apk",
    "app", "sh", "bash", "pif", "lnk", "reg", "cpl", "msc", "gadget", "so", "dylib", "bin", "elf", "py", "pyc", "php",
}

# (magic prefix, mime). Checked in order.
_MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
    (b"{\\rtf", "application/rtf"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/x-ole"),          # legacy .doc / .xls
]
# Binary-only signatures (ELF, Mach-O, Java class). "MZ" (Windows) and "#!" (scripts) are checked separately
# because an ordinary text file can start with those characters.
_EXECUTABLE_MAGIC = (b"\x7fELF", b"\xfe\xed\xfa", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe")

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TEXT = "text/plain"

# extension -> mimes its content may legitimately be
_EXPECTED = {
    "pdf": {"application/pdf"},
    "png": {"image/png"}, "jpg": {"image/jpeg"}, "jpeg": {"image/jpeg"}, "gif": {"image/gif"}, "bmp": {"image/bmp"},
    "tif": {"image/tiff"}, "tiff": {"image/tiff"},
    "webp": {"image/webp"},
    "docx": {DOCX}, "xlsx": {XLSX}, "doc": {"application/x-ole"}, "xls": {"application/x-ole"},
    "rtf": {"application/rtf"},
    "txt": {TEXT}, "md": {TEXT}, "csv": {TEXT}, "json": {TEXT}, "log": {TEXT},
}


def _is_text(head: bytes) -> bool:
    """Plain text in any encoding (UTF-8, UTF-16 with a BOM, Windows-1252 ...): no NUL bytes and almost no control
    characters. Real binaries contain NULs or far more control bytes."""
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    if b"\x00" in head:
        return False
    controls = sum(1 for b in head if b < 32 and b not in (9, 10, 12, 13))
    return controls <= max(2, len(head) // 100)


def _ooxml_kind(content: bytes) -> Optional[str]:
    """A .docx / .xlsx is a zip with a known folder; look at the names only (nothing is extracted)."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            names = z.namelist()
    except (zipfile.BadZipFile, OSError):
        return None
    if "[Content_Types].xml" not in names:
        return None
    if any(n.startswith("word/") for n in names):
        return DOCX
    if any(n.startswith("xl/") for n in names):
        return XLSX
    return None


def sniff_mime(content: bytes) -> str:
    """Detected type from the bytes: a mime string, "application/x-executable", or "application/octet-stream"."""
    head = content[:8192]
    if head.startswith(_EXECUTABLE_MAGIC) or (head.startswith(b"MZ") and not _is_text(head)) or head.startswith(b"#!"):
        return "application/x-executable"
    if b"%PDF-" in head[:1024]:                      # the PDF spec allows junk before the header (scanners add it)
        return "application/pdf"
    for magic, mime in _MAGIC:
        if head.startswith(magic):
            return mime
    if head[:2] == b"BM" and head[6:10] == bytes(4):
        return "image/bmp"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"PK\x03\x04"):
        return _ooxml_kind(content) or "application/zip"
    return TEXT if _is_text(head) else "application/octet-stream"


def validate_upload(filename: str, content: bytes, max_bytes: Optional[int] = None) -> str:
    """Raises `UploadRejected` for an empty, oversized, executable or mislabelled file; returns the detected mime."""
    limit = max_bytes if max_bytes is not None else settings.upload_max_mb * 1024 * 1024
    if not content:
        raise UploadRejected("The file is empty.")
    if len(content) > limit:
        raise UploadRejected(f"The file is larger than the {limit // (1024 * 1024)} MB limit.", 413)
    ext = _extension(filename)
    mime = sniff_mime(content)
    if mime == "application/x-executable" or ext in _EXECUTABLE_EXTENSIONS:
        raise UploadRejected("Programs and scripts cannot be uploaded.", 415)
    expected = _EXPECTED.get(ext)
    if expected is None:
        raise UploadRejected(f"Files of type '.{ext or '?'}' are not supported.", 415)
    if mime not in expected:
        raise UploadRejected(f"This file does not look like a real .{ext} file (its content is {mime.split('/')[-1]}).", 415)
    return mime


# ------------------------------------------------------------------ saving / deleting

def _org_folder(organization_id: Optional[uuid.UUID]) -> str:
    return os.path.join(UPLOAD_DIR, str(organization_id) if organization_id else "shared")


def _find_existing(folder: str, digest: str, content: bytes) -> Optional[str]:
    """A stored file in `folder` with exactly this content (hash prefix in the name, then a byte comparison)."""
    try:
        names = os.listdir(folder)
    except FileNotFoundError:
        return None
    for name in names:
        if name.startswith(digest[:_HASH_CHARS] + "_") and not name.endswith((_REFS_SUFFIX, ".tmp")):
            path = os.path.join(folder, name)
            try:
                if os.path.getsize(path) == len(content):
                    with open(path, "rb") as f:
                        if f.read() == content:
                            return path
            except OSError:
                continue
    return None


def _read_refs(path: str) -> int:
    try:
        with open(path + _REFS_SUFFIX, "r", encoding="ascii") as f:
            return max(1, int(f.read().strip() or 1))
    except (FileNotFoundError, ValueError):
        return 1


def _write_refs(path: str, count: int) -> None:
    if count <= 1:
        try:
            os.remove(path + _REFS_SUFFIX)
        except FileNotFoundError:
            pass
        return
    with open(path + _REFS_SUFFIX, "w", encoding="ascii") as f:
        f.write(str(count))


def _store(filename: str, content: bytes, organization_id: Optional[uuid.UUID]) -> str:
    folder = _org_folder(organization_id)
    digest = hashlib.sha256(content).hexdigest()
    with _lock:
        os.makedirs(folder, exist_ok=True)
        existing = _find_existing(folder, digest, content)
        if existing:
            _write_refs(existing, _read_refs(existing) + 1)
            logger.info("duplicate upload: reusing %s", existing)
            return existing
        path = os.path.join(folder, f"{digest[:_HASH_CHARS]}_{safe_filename(filename)}")
        tmp = f"{path}.{uuid.uuid4().hex[:6]}.tmp"
        with open(tmp, "wb") as f:
            f.write(content)
        os.replace(tmp, path)
        return path


async def save_file(filename: str, content: bytes, organization_id: Optional[uuid.UUID] = None) -> str:
    """
    Validates and stores the file as uploads/<org>/<content-hash>_<safe name>; returns the stored path.
    Uploading identical bytes again returns the same path (and counts one more reference to it).
    Raises `UploadRejected` for a file that must not be stored.
    """
    validate_upload(filename, content)
    return await asyncio.to_thread(_store, filename, content, organization_id)


def _delete(storage_path: str) -> None:
    with _lock:
        refs = _read_refs(storage_path)
        if refs > 1:
            _write_refs(storage_path, refs - 1)
            return
        for p in (storage_path, storage_path + _REFS_SUFFIX):
            try:
                os.remove(p)
            except FileNotFoundError:
                pass


async def delete_file(storage_path: str) -> None:
    """Drops one reference; the file itself goes when the last record using it is deleted."""
    try:
        await asyncio.to_thread(_delete, storage_path)
    except Exception as e:
        logger.warning("Failed to delete file %s: %s", storage_path, e)


async def read_file(storage_path: str) -> bytes:
    async with aiofiles.open(storage_path, "rb") as f:
        return await f.read()


# ------------------------------------------------------------------ housekeeping

@dataclass
class CleanupReport:
    removed: list[str]
    bytes_freed: int
    kept_recent: int


def cleanup_orphans(known_paths: Iterable[str], older_than_hours: float = 24.0, dry_run: bool = False,
                    organization_id: Optional[uuid.UUID] = None) -> CleanupReport:
    """Deletes stored files that no record references (`known_paths` = every path in the database) and half-written
    `.tmp` files, once they are older than `older_than_hours` (so an upload in progress is never touched).
    Restrict to one organisation with `organization_id`. `dry_run` only reports."""
    keep = {os.path.abspath(p) for p in known_paths}
    cutoff = time.time() - older_than_hours * 3600
    root = _org_folder(organization_id) if organization_id else UPLOAD_DIR
    removed: list[str] = []
    freed = recent = 0
    with _lock:
        for folder, _dirs, files in os.walk(root):
            for name in files:
                path = os.path.join(folder, name)
                real = path[: -len(_REFS_SUFFIX)] if name.endswith(_REFS_SUFFIX) else path
                if os.path.abspath(real) in keep:
                    continue
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                if st.st_mtime > cutoff:
                    recent += 1
                    continue
                removed.append(path)
                freed += st.st_size
                if not dry_run:
                    try:
                        os.remove(path)
                    except OSError as e:
                        logger.warning("cleanup could not remove %s: %s", path, e)
    return CleanupReport(removed=removed, bytes_freed=freed, kept_recent=recent)
