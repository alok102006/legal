import logging
import os
import re
import uuid
from typing import Optional

import aiofiles

logger = logging.getLogger("legalos.storage")

# Directory for storing uploaded files locally
UPLOAD_DIR = "./uploads"

_SAFE = re.compile(r"[^A-Za-z0-9._ \-()]+")


def safe_filename(filename: str) -> str:
    """Keeps only harmless characters; never returns an empty or hidden name."""
    base = os.path.basename((filename or "").replace("\\", "/")) or "file"
    base = _SAFE.sub("_", base).strip(" .") or "file"
    return base[:120]


async def save_file(filename: str, content: bytes, organization_id: Optional[uuid.UUID] = None) -> str:
    """
    Saves file bytes under uploads/<org>/<uuid>_<name>. The uuid prefix prevents two uploads
    with the same filename from overwriting each other. Returns the stored path.
    """
    folder = os.path.join(UPLOAD_DIR, str(organization_id) if organization_id else "shared")
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"{uuid.uuid4().hex[:12]}_{safe_filename(filename)}")

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    return file_path


async def delete_file(storage_path: str) -> None:
    """Removes a file from local storage."""
    try:
        if os.path.exists(storage_path):
            os.remove(storage_path)
    except Exception as e:
        logger.warning("Failed to delete file %s: %s", storage_path, e)
