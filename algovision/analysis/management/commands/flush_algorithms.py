"""Remove all Algorithm rows and clear MEDIA_ROOT/algorithms (ZIPs + extract dirs only)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from analysis.models import Algorithm


class Command(BaseCommand):
    help = (
        "Delete every Algorithm row and remove all files/directories under MEDIA_ROOT/algorithms/ "
        "(including algorithms/pkg/<pk>/ ZIPs and extract trees). "
        "Does not delete uploads, outputs, Execution, or Output rows "
        "(Execution.algorithm becomes NULL)."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be deleted without changing the database or disk.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        alg_dir = Path(settings.MEDIA_ROOT) / "algorithms"

        qs = Algorithm.objects.all()
        n_alg = qs.count()
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Dry run: would delete {n_alg} Algorithm row(s).")
            )
        else:
            with transaction.atomic():
                qs.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {n_alg} Algorithm row(s).")
            )

        if not alg_dir.is_dir():
            self.stdout.write(
                "Algorithms media folder missing or not a directory; "
                f"skipped disk cleanup ({alg_dir})."
            )
            return

        children = sorted(alg_dir.iterdir(), key=lambda p: p.name)
        if not children:
            self.stdout.write("No files or folders under algorithms/ to remove.")
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: would remove {len(children)} path(s) under {alg_dir}:"
                )
            )
            for child in children:
                self.stdout.write(f"  {child}")
            return

        removed = 0
        for child in children:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
            removed += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {removed} file(s) or director(ies) from {alg_dir}."
            )
        )
