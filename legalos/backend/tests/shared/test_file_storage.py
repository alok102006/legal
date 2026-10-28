import io
import os
import uuid
import zipfile

import pytest

from app.config import settings
from app.shared.storage import file_storage as fs

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def _zip(*names) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, "<x/>")
    return buf.getvalue()


DOCX = _zip("[Content_Types].xml", "word/document.xml")
XLSX = _zip("[Content_Types].xml", "xl/workbook.xml")


@pytest.fixture(autouse=True)
def _upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "UPLOAD_DIR", str(tmp_path / "uploads"))


ORG_A, ORG_B = uuid.uuid4(), uuid.uuid4()


# ------------------------------------------------------------------ names

@pytest.mark.parametrize("raw,expected", [
    ("../../etc/passwd", "passwd"),
    ("C:\\Users\\x\\contract.pdf", "contract.pdf"),
    ("  .hidden.pdf ", "hidden.pdf"),
    ("a/b\\c.txt", "c.txt"),
    ("", "file"),
    ("..", "file"),
    ("con.txt", "_con.txt"),
    ("na\x00me\n.pdf", "na_me_.pdf"),
])
def test_safe_filename(raw, expected):
    assert fs.safe_filename(raw) == expected


def test_safe_filename_keeps_devanagari_and_limits_length():
    assert fs.safe_filename("अनुबंध पत्र.pdf") == "अनुबंध पत्र.pdf"
    long = fs.safe_filename("a" * 400 + ".pdf")
    assert len(long) <= 120 and long.endswith(".pdf")


# ------------------------------------------------------------------ sniffing / validation

@pytest.mark.parametrize("content,mime", [
    (PDF, "application/pdf"), (b"\r\n\r\n" + PDF, "application/pdf"), (PNG, "image/png"), (JPG, "image/jpeg"), (DOCX, fs.DOCX), (XLSX, fs.XLSX),
    ("हिंदी text".encode("utf-8"), "text/plain"), ("caf\xe9 agreement".encode("cp1252"), "text/plain"),
    (b"MZ Industries agreement text", "text/plain"),          # ordinary text that happens to start with MZ
    (b"MZ\x90\x00\x03\x00\x00\x00", "application/x-executable"),
    (b"\x7fELF\x02\x01\x01", "application/x-executable"),
    (b"#!/bin/sh\necho hi", "application/x-executable"),
    (_zip("a.txt"), "application/zip"),
    (bytes(range(256)) * 4, "application/octet-stream"),
])
def test_sniff_mime(content, mime):
    assert fs.sniff_mime(content) == mime


def test_valid_uploads_pass():
    for name, data in [("a.pdf", PDF), ("a.docx", DOCX), ("a.xlsx", XLSX), ("a.txt", b"hello"), ("a.PNG", PNG), ("scan.jpeg", JPG)]:
        assert fs.validate_upload(name, data)


@pytest.mark.parametrize("name,data,status", [
    ("virus.exe", b"MZ\x90\x00", 415),
    ("renamed.pdf", b"MZ\x90\x00\x03\x00", 415),               # executable disguised as a pdf
    ("run.sh", b"echo hi", 415),
    ("notes.js", b"alert(1)", 415),
    ("fake.pdf", b"not really a pdf", 415),
    ("fake.docx", b"hello", 415),
    ("fake.docx", _zip("a.txt"), 415),                          # a zip is not a docx
    ("data.xyz", b"hello", 415),
    ("noext", b"hello", 415),
    ("empty.txt", b"", 400),
])
def test_rejected_uploads(name, data, status):
    with pytest.raises(fs.UploadRejected) as e:
        fs.validate_upload(name, data)
    assert e.value.status_code == status


def test_size_limit_comes_from_config(monkeypatch):
    monkeypatch.setattr(settings, "upload_max_mb", 1)
    fs.validate_upload("ok.txt", b"x" * 1024 * 1024)
    with pytest.raises(fs.UploadRejected) as e:
        fs.validate_upload("big.txt", b"x" * (1024 * 1024 + 1))
    assert e.value.status_code == 413 and "1 MB" in e.value.detail


# ------------------------------------------------------------------ saving, org folders, dedupe

async def test_save_uses_per_org_folders_and_safe_names():
    path = await fs.save_file("../../evil name.pdf", PDF, ORG_A)
    assert os.path.dirname(path).endswith(str(ORG_A)) and os.path.basename(path).endswith("_evil name.pdf")
    assert os.path.exists(path) and open(path, "rb").read() == PDF
    shared = await fs.save_file("a.txt", b"hello")
    assert os.path.dirname(shared).endswith("shared")


async def test_same_content_twice_returns_the_same_path():
    first = await fs.save_file("contract.pdf", PDF, ORG_A)
    second = await fs.save_file("renamed-copy.pdf", PDF, ORG_A)
    assert first == second
    assert len(os.listdir(os.path.dirname(first))) == 2          # the file and its reference counter, nothing else


async def test_same_content_in_another_org_is_stored_separately():
    a = await fs.save_file("c.pdf", PDF, ORG_A)
    b = await fs.save_file("c.pdf", PDF, ORG_B)
    assert a != b and os.path.exists(a) and os.path.exists(b)


async def test_different_content_with_the_same_name_does_not_overwrite():
    a = await fs.save_file("c.txt", b"first", ORG_A)
    b = await fs.save_file("c.txt", b"second", ORG_A)
    assert a != b and open(a, "rb").read() == b"first" and open(b, "rb").read() == b"second"


async def test_deleting_one_of_two_records_keeps_the_shared_file():
    path = await fs.save_file("c.pdf", PDF, ORG_A)
    assert await fs.save_file("c2.pdf", PDF, ORG_A) == path          # two records now use it
    await fs.delete_file(path)                                       # first record deleted
    assert os.path.exists(path)
    await fs.delete_file(path)                                       # last record deleted
    assert not os.path.exists(path) and not os.path.exists(path + ".refs")


async def test_delete_of_a_missing_file_is_silent():
    await fs.delete_file(os.path.join(fs.UPLOAD_DIR, "nope.pdf"))


async def test_save_rejects_bad_files_before_writing():
    with pytest.raises(fs.UploadRejected):
        await fs.save_file("virus.exe", b"MZ\x90\x00", ORG_A)
    assert not os.path.exists(os.path.join(fs.UPLOAD_DIR, str(ORG_A)))


async def test_read_file_roundtrip():
    path = await fs.save_file("a.txt", b"hello", ORG_A)
    assert await fs.read_file(path) == b"hello"


# ------------------------------------------------------------------ cleanup

async def test_cleanup_removes_only_old_orphans():
    keep = await fs.save_file("keep.txt", b"keep", ORG_A)
    old_orphan = await fs.save_file("old.txt", b"old", ORG_A)
    fresh_orphan = await fs.save_file("fresh.txt", b"fresh", ORG_A)
    stale_tmp = os.path.join(os.path.dirname(keep), "x.tmp")
    open(stale_tmp, "w").write("half")
    for p in (old_orphan, stale_tmp):
        os.utime(p, (1000, 1000))

    dry = fs.cleanup_orphans([keep], older_than_hours=1, dry_run=True)
    assert set(dry.removed) == {old_orphan, stale_tmp} and os.path.exists(old_orphan)

    report = fs.cleanup_orphans([keep], older_than_hours=1)
    assert set(report.removed) == {old_orphan, stale_tmp} and report.bytes_freed > 0 and report.kept_recent == 1
    assert os.path.exists(keep) and os.path.exists(fresh_orphan) and not os.path.exists(old_orphan)


async def test_cleanup_can_be_limited_to_one_organisation():
    a = await fs.save_file("a.txt", b"a", ORG_A)
    b = await fs.save_file("b.txt", b"b", ORG_B)
    for p in (a, b):
        os.utime(p, (1000, 1000))
    fs.cleanup_orphans([], older_than_hours=1, organization_id=ORG_A)
    assert not os.path.exists(a) and os.path.exists(b)
