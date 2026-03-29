import os
import uuid

from django.contrib import messages
from django.http import HttpRequest

from typing import Any, List

from .models import FileType


def is_size_valid(file: Any, max_size: int, request: HttpRequest):
    # Check size is not None and less than max_size (converted to bytes)
    if file.size == None:
        messages.error(
            request,
            f"El archivo '{file.name}' no es válido."
        )
        return False
    if file.size > max_size:
        messages.error(
            request,
            f"El archivo '{file.name}' supera el límite de {max_size} MB."
        )
        return True


def is_type_valid(file: Any, request: HttpRequest):
    # Check if content_type is available and starts with 'image/' or 'video/', or if the file name ends with '.csv'
    file_type = getattr(file, 'content_type', None)
    if not file_type or not (
        file_type.startswith('image/') or
        file_type.startswith('video/') or
        file.name.endswith('.csv')
    ):
        messages.error(
            request, f"Archivo '{file.name}' no permitido.")
        return False
    return True


def extension_getter(file: Any):
    file_type = getattr(file, 'content_type', None)
    # File type extension getter
    type_code = None
    # Type: video/mp4 or image/jpeg
    if file_type and (file_type.split("/")[0] == "image" or file_type.split("/")[0] == "video"):
        type_code, _ = file_type.split("/")
    else:
        # If it's not image or video, we should check if have a csv
        if file_type:
            _, type_code = file_type.split("/")
    return FileType.objects.get(code=type_code)


def name_change(file: Any, existing_files: List[str]):
    base_name, ext = os.path.splitext(file.name)
    final_name = file.name
    was_renamed = False
    if final_name in existing_files:
        final_name = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"
        was_renamed = True
        file.name = final_name

    return file.name, was_renamed
