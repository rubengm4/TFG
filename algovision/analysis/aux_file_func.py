import os
import uuid
from typing import Any, List, Optional, Tuple

import magic
from django.contrib import messages
from django.http import HttpRequest

from .models import FileType, sanitize_uploaded_filename

ALLOWED_MIME_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "video/mp4",
    "text/csv",
    "text/plain",
})

MIME_TO_TYPE_CODE = {
    "image/jpeg": "image",
    "image/png": "image",
    "video/mp4": "video",
    "text/csv": "csv",
    "text/plain": "csv",
}

MIME_TO_STORAGE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "video/mp4": ".mp4",
    "text/csv": ".csv",
    "text/plain": ".csv",
}


def upload_client_filename_errors(name: Optional[str]) -> Optional[str]:
    """
    Reject client-supplied multipart filenames that are empty, too long,
    contain path separators, '..', NUL, or ASCII control characters.
    """
    if name is None or not str(name).strip():
        return "nombre vacío o inválido."
    name = str(name).strip()
    if len(name) > 255:
        name = name[:255]
    if "\x00" in name:
        return "el nombre contiene caracteres no permitidos."
    if any(ord(c) < 32 for c in name):
        return "el nombre contiene caracteres no permitidos."
    if "/" in name or "\\" in name:
        return "no se permiten rutas en el nombre del archivo."
    if ".." in name:
        return "la secuencia '..' no está permitida en el nombre."
    return None


def sniff_uploaded_mime(file: Any) -> Optional[str]:
    try:
        chunk = file.read(2048)
        file.seek(0)
        mime = magic.from_buffer(chunk, mime=True)
        if isinstance(mime, bytes):
            mime = mime.decode("utf-8", errors="replace")
        return mime
    except Exception:
        try:
            file.seek(0)
        except Exception:
            pass
        return None


def is_size_valid(file: Any, max_size: int, request: HttpRequest) -> bool:
    if file.size is None:
        messages.error(
            request,
            f"El archivo '{file.name}' no es válido."
        )
        return False
    if file.size > max_size:
        limit_mb = max_size / (1024 * 1024)
        messages.error(
            request,
            f"El archivo '{file.name}' supera el límite de {limit_mb:g} MB."
        )
        return False
    return True


def validate_upload_mime(file: Any, request: HttpRequest) -> Optional[str]:
    """Return MIME type if allowed; otherwise show a message and return None."""
    label = getattr(file, "name", "") or "archivo"
    mime = sniff_uploaded_mime(file)
    if not mime or mime not in ALLOWED_MIME_TYPES:
        messages.error(
            request,
            f"Archivo '{label}' no permitido.",
        )
        return None
    return mime


def file_type_for_mime(mime: str) -> FileType:
    code = MIME_TO_TYPE_CODE[mime]
    return FileType.objects.get(code=code)


def storage_name_for_mime(mime: str) -> str:
    ext = MIME_TO_STORAGE_EXT[mime]
    return f"{uuid.uuid4().hex}{ext}"


def display_name_for_new_upload(
    original_client_name: str,
    canonical_ext: str,
    existing_display_names: List[str],
) -> Tuple[str, bool]:
    """
    Build a user-visible filename from the (already validated) client name,
    using the extension derived from content sniffing. Resolve collisions
    against existing_display_names (updated in-place for batch uploads).
    """
    base, _ = os.path.splitext(
        sanitize_uploaded_filename(os.path.basename(original_client_name))
    )
    if not base:
        base = f"file_{uuid.uuid4().hex[:8]}"
    candidate = f"{base}{canonical_ext}"
    was_renamed = False
    if candidate in existing_display_names:
        candidate = f"{base}_{uuid.uuid4().hex[:8]}{canonical_ext}"
        was_renamed = True
    existing_display_names.append(candidate)
    return candidate, was_renamed
