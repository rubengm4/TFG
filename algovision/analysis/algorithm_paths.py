"""Stable on-disk layout for algorithm ZIPs and Celery extract dirs."""

from __future__ import annotations

import shutil
from pathlib import Path

_PKG = "pkg"


def algorithm_pkg_disk_root(media_root: str | Path, pk: int) -> Path:
    return Path(media_root) / "algorithms" / _PKG / str(pk)


def algorithm_extract_disk_path(media_root: str | Path, pk: int) -> Path:
    return algorithm_pkg_disk_root(media_root, pk) / "extract"


def remove_legacy_extract_next_to_zip(media_root: str | Path, zip_abs: Path) -> None:
    """Remove ``algorithms/<stem>/`` cache dirs from the pre-pkg layout (best-effort)."""
    root = Path(media_root) / "algorithms"
    try:
        rel = zip_abs.relative_to(root)
    except ValueError:
        return
    parts = rel.parts
    if parts and parts[0] == _PKG:
        return
    stem_dir = root / zip_abs.stem
    if stem_dir.is_dir():
        shutil.rmtree(stem_dir, ignore_errors=True)
