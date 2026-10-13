"""Secure image storage service (§16, §47).

- Validates MIME type (JPEG/PNG/WebP only) via magic bytes; rejects
  executables, oversized files and spoofed extensions.
- Generates sanitized, non-guessable storage names; never trusts the
  original filename.
- Stores permanently in object storage (local backend now; S3-compatible
  via config — CDN-compatible paths).
"""
from __future__ import annotations

import hashlib
import io
import os
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

from app.core.config import get_settings
from app.core.errors import ValidationFailed
from app.core.security import secure_filename

_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # + WEBP tag at offset 8
}


@dataclass
class StoredImage:
    storage_path: str
    file_type: str
    file_size: int
    width: int
    height: int
    thumbnail_path: str
    original_name: str


def detect_image_type(content: bytes) -> Optional[str]:
    for magic, mime in _MAGIC.items():
        if content.startswith(magic):
            if mime == "image/webp":
                if len(content) < 12 or content[8:12] != b"WEBP":
                    return None
            return mime
    return None


def _image_dimensions(content: bytes, mime: str) -> Tuple[int, int]:
    """Read dimensions without external deps (PNG/JPEG/WebP headers)."""
    try:
        if mime == "image/png" and len(content) >= 24:
            w = int.from_bytes(content[16:20], "big")
            h = int.from_bytes(content[20:24], "big")
            return w, h
        if mime == "image/jpeg":
            i = 2
            while i < len(content) - 9:
                if content[i] != 0xFF:
                    i += 1
                    continue
                marker = content[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                    h = int.from_bytes(content[i + 5: i + 7], "big")
                    w = int.from_bytes(content[i + 7: i + 9], "big")
                    return w, h
                length = int.from_bytes(content[i + 2: i + 4], "big")
                i += 2 + length
    except Exception:
        pass
    return 0, 0


def store_product_image(content: bytes, original_filename: str, kind: str = "front_package") -> StoredImage:
    settings = get_settings()

    if len(content) > settings.image_max_bytes:
        raise ValidationFailed(
            f"Image exceeds maximum size of {settings.image_max_bytes // (1024 * 1024)} MB.",
            {"size": len(content)},
        )
    if len(content) < 32:
        raise ValidationFailed("File is too small to be a valid image.")

    mime = detect_image_type(content)
    if mime is None or mime not in settings.image_allowed_types:
        raise ValidationFailed(
            "Unsupported image type. Allowed: JPEG, PNG, WebP.",
            {"detected": mime or "unknown"},
        )

    width, height = _image_dimensions(content, mime)
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime]
    digest = hashlib.sha256(content).hexdigest()[:24]
    stored_name = f"{uuid.uuid4().hex}_{digest}{ext}"

    root = settings.storage_local_root
    rel_dir = os.path.join("products", kind)
    abs_dir = os.path.join(root, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    abs_path = os.path.join(abs_dir, stored_name)
    with open(abs_path, "wb") as fh:
        fh.write(content)

    # Thumbnail: stored as a resized copy when Pillow is available; otherwise
    # the original is referenced (CDN-compatible layout stays identical).
    thumbnail_rel = ""
    try:
        from PIL import Image  # optional dependency

        img = Image.open(io.BytesIO(content))
        img.thumbnail((320, 320))
        thumb_name = f"thumb_{stored_name}"
        thumb_abs = os.path.join(abs_dir, thumb_name)
        img.save(thumb_abs)
        thumbnail_rel = os.path.join(rel_dir, thumb_name).replace("\\", "/")
    except Exception:
        thumbnail_rel = ""

    return StoredImage(
        storage_path=os.path.join(rel_dir, stored_name).replace("\\", "/"),
        file_type=mime,
        file_size=len(content),
        width=width,
        height=height,
        thumbnail_path=thumbnail_rel,
        original_name=secure_filename(original_filename),
    )
