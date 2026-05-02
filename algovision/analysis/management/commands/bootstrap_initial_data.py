"""Idempotent bootstrap: default projects, optional first superuser, superuser↔project links."""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from analysis.models import Project, UserProject

logger = logging.getLogger(__name__)

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


class Command(BaseCommand):
    help = (
        "Ensure default projects exist; create superuser if DB has no users and "
        "DJANGO_SUPERUSER_* env vars are set; link all superusers to all default projects."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        self._ensure_default_projects()
        self._ensure_initial_superuser()
        self._ensure_superuser_project_memberships()

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
