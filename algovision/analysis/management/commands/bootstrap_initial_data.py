"""Idempotent bootstrap: default projects, optional first superuser, superuser↔project links."""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from analysis.models import Algorithm, FileType, Project, UserProject

logger = logging.getLogger(__name__)

# Codes must match analysis.aux_file_func.MIME_TO_TYPE_CODE (image/jpeg|png, video/mp4, text/csv|plain)
DEFAULT_FILE_TYPES: tuple[tuple[str, str], ...] = (
    ("image", "Imagen"),
    ("video", "Vídeo"),
    ("csv", "CSV"),
)

# Titles must match session `login_source` / homepage form values in templates/index.html
DEFAULT_PROJECTS: tuple[tuple[str, str, date], ...] = (
    (
        "pv-analysis",
        "Gestión de algoritmos de detección de paneles fotovoltaicos.",
        date(2025, 1, 1),
    ),
    (
        "people-analysis",
        "Gestión de algoritmos para análisis de personas en interiores.",
        date(2025, 1, 1),
    ),
    (
        "stats-analysis",
        "Generación de estadísticas y tendencias a partir de archivos CSV.",
        date(2025, 1, 1),
    ),
)


_MANIFEST_KEYS = frozenset({
    "name",
    "version",
    "description",
    "zip",
    "project_title",
    "entrypoint",
    "supported_codes",
    "requires_two_files",
    "input_is_dir",
})


class Command(BaseCommand):
    help = (
        "Ensure default FileTypes, projects, and seed Algorithms "
        "(ZIPs saved as MEDIA_ROOT/algorithms/pkg/<pk>/archive.zip from media/ or bundled_algorithms); "
        "optional superuser; project links."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        self._ensure_default_file_types()
        self._ensure_default_projects()
        self._ensure_seed_algorithms()
        self._ensure_initial_superuser()
        self._ensure_superuser_project_memberships()

    def _ensure_default_file_types(self) -> None:
        for code, name in DEFAULT_FILE_TYPES:
            _, created = FileType.objects.get_or_create(
                code=code,
                defaults={"name": name},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created FileType: {code}"))
            else:
                self.stdout.write(f"FileType already exists: {code}")

    def _ensure_default_projects(self) -> None:
        for title, description, start_date in DEFAULT_PROJECTS:
            _, created = Project.objects.get_or_create(
                title=title,
                defaults={
                    "description": description,
                    "start_date": start_date,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created project: {title}"))
            else:
                self.stdout.write(f"Project already exists: {title}")

    def _algorithm_manifest_path(self) -> Path:
        return Path(settings.BASE_DIR) / "analysis" / "seeds" / "algorithms_manifest.yaml"

    def _bundled_algorithms_dir(self) -> Path:
        return Path(settings.BASE_DIR) / "analysis" / "seeds" / "bundled_algorithms"

    def _load_seed_algorithms(self) -> tuple[dict[str, Any], ...]:
        path = self._algorithm_manifest_path()
        if not path.is_file():
            self.stdout.write(
                self.style.WARNING(
                    f"No algorithm manifest at {path}; skipping algorithm seed."
                )
            )
            return ()
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not data or not isinstance(data.get("algorithms"), list):
            self.stdout.write(
                self.style.WARNING(
                    "Manifest missing top-level 'algorithms' list; skipping algorithm seed."
                )
            )
            return ()
        out: list[dict[str, Any]] = []
        for i, row in enumerate(data["algorithms"]):
            if not isinstance(row, dict):
                self.stdout.write(
                    self.style.WARNING(f"Manifest algorithms[{i}] is not a mapping; skip.")
                )
                continue
            missing = _MANIFEST_KEYS - frozenset(row.keys())
            if missing:
                self.stdout.write(
                    self.style.WARNING(
                        f"Manifest algorithms[{i}] missing keys {sorted(missing)}; skip."
                    )
                )
                continue
            codes = row["supported_codes"]
            if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes):
                self.stdout.write(
                    self.style.WARNING(
                        f"Manifest algorithms[{i}] supported_codes must be a list of strings; skip."
                    )
                )
                continue
            out.append(
                {
                    "name": row["name"],
                    "version": str(row["version"]),
                    "description": str(row["description"]),
                    "zip": row["zip"],
                    "project_title": row["project_title"],
                    "entrypoint": row["entrypoint"],
                    "supported_codes": tuple(codes),
                    "requires_two_files": bool(row["requires_two_files"]),
                    "input_is_dir": bool(row.get("input_is_dir", False)),
                }
            )
        return tuple(out)

    def _ensure_seed_algorithms(self) -> None:
        alg_dir = Path(settings.MEDIA_ROOT) / "algorithms"
        alg_dir.mkdir(parents=True, exist_ok=True)
        bundled_dir = self._bundled_algorithms_dir()

        for spec in self._load_seed_algorithms():
            zip_name = spec["zip"]
            zip_path = alg_dir / zip_name
            try:
                project = Project.objects.get(title=spec["project_title"])
            except Project.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"bootstrap_initial_data: project {spec['project_title']!r} missing; "
                        f"skip algorithm {spec['name']!r}"
                    )
                )
                continue

            exists = Algorithm.objects.filter(
                name=spec["name"],
                version=spec["version"],
                project=project,
            ).exists()
            if exists:
                self.stdout.write(f"Algorithm already exists: {spec['name']} ({spec['version']})")
                continue

            bundled_zip = bundled_dir / zip_name
            if zip_path.is_file():
                source_zip = zip_path
            elif bundled_zip.is_file():
                source_zip = bundled_zip
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"No ZIP at {zip_path} and none at {bundled_zip}; "
                        f"skip creating Algorithm {spec['name']!r}"
                    )
                )
                continue

            fts = list(FileType.objects.filter(code__in=spec["supported_codes"]))
            if len(fts) != len(spec["supported_codes"]):
                missing = set(spec["supported_codes"]) - {ft.code for ft in fts}
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing FileType codes {missing}; skip {spec['name']!r}"
                    )
                )
                continue

            with transaction.atomic():
                algo = Algorithm(
                    name=spec["name"],
                    version=spec["version"],
                    description=spec["description"],
                    project=project,
                    entrypoint=spec["entrypoint"],
                    requires_two_files=spec["requires_two_files"],
                    input_is_dir=spec["input_is_dir"],
                )
                algo.save()
                with source_zip.open("rb") as fh:
                    algo.archive.save("archive.zip", File(fh), save=True)
                algo.supported_types.set(fts)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created Algorithm {spec['name']} → algorithms/pkg/{algo.pk}/archive.zip "
                    f"(from {zip_name})"
                )
            )

    def _ensure_initial_superuser(self) -> None:
        User = get_user_model()
        if User.objects.exists():
            return

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")

        if not (username and email and password):
            self.stdout.write(
                self.style.WARNING(
                    "No users in database and DJANGO_SUPERUSER_USERNAME / "
                    "DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD not all set; "
                    "skipping superuser creation."
                )
            )
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Created initial superuser: {username}"))

    def _ensure_superuser_project_memberships(self) -> None:
        User = get_user_model()
        titles = [t for t, _, _ in DEFAULT_PROJECTS]
        projects = list(Project.objects.filter(title__in=titles))
        if not projects:
            logger.warning("bootstrap_initial_data: no default projects to link")
            return

        today = timezone.now().date()
        supers = User.objects.filter(is_superuser=True)
        count = 0
        with transaction.atomic():
            for user in supers:
                for project in projects:
                    _, created = UserProject.objects.get_or_create(
                        project=project,
                        user=user,
                        defaults={"joined_at": today},
                    )
                    if created:
                        count += 1
        if count:
            self.stdout.write(
                self.style.SUCCESS(f"Linked superusers to projects ({count} new UserProject rows).")
            )
