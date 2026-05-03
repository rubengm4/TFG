"""Repair seed Algorithm archives by copying from bundled_algorithms when media is missing."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction

from analysis.management.commands.bootstrap_initial_data import Command as BootstrapCommand
from analysis.models import Algorithm, Project


class Command(BaseCommand):
    help = (
        "For each algorithm defined in algorithms_manifest.yaml: if the matching DB row exists "
        "but default_storage does not have the archive file, copy the ZIP from "
        "analysis/seeds/bundled_algorithms/<zip> into MEDIA_ROOT/algorithms/ and re-save "
        "the FileField. Does not affect algorithms not listed in the manifest."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print actions only; do not copy files or update the database.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        bootstrap = BootstrapCommand()
        bootstrap.stdout = self.stdout
        specs = bootstrap._load_seed_algorithms()
        bundled_dir = bootstrap._bundled_algorithms_dir()
        alg_dir = Path(settings.MEDIA_ROOT) / "algorithms"
        alg_dir.mkdir(parents=True, exist_ok=True)

        repaired = 0
        skipped_ok = 0
        skipped_no_bundle = 0
        skipped_no_row = 0

        for spec in specs:
            zip_name = spec["zip"]
            try:
                project = Project.objects.get(title=spec["project_title"])
            except Project.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skip {spec['name']!r}: project {spec['project_title']!r} missing"
                    )
                )
                continue

            algo = Algorithm.objects.filter(
                name=spec["name"],
                version=spec["version"],
                project=project,
            ).first()
            if algo is None:
                self.stdout.write(
                    f"No DB row for seed {spec['name']!r} ({spec['version']}); skipping."
                )
                skipped_no_row += 1
                continue

            name_field = algo.archive.name if algo.archive else ""
            if name_field and default_storage.exists(name_field):
                self.stdout.write(
                    f"OK {spec['name']}: archive exists ({name_field})"
                )
                skipped_ok += 1
                continue

            bundled_zip = bundled_dir / zip_name
            if not bundled_zip.is_file():
                self.stdout.write(
                    self.style.WARNING(
                        f"Missing media for {spec['name']!r} but no bundle file: {bundled_zip}"
                    )
                )
                skipped_no_bundle += 1
                continue

            dest_disk = alg_dir / zip_name
            self.stdout.write(
                self.style.NOTICE(
                    f"Repair {spec['name']!r}: copy {bundled_zip} -> {dest_disk}"
                )
            )
            if dry_run:
                repaired += 1
                continue

            shutil.copy2(bundled_zip, dest_disk)
            with transaction.atomic():
                with dest_disk.open("rb") as fh:
                    algo.archive.save(zip_name, File(fh), save=False)
                algo.save()
            repaired += 1
            self.stdout.write(
                self.style.SUCCESS(f"  saved FileField as algorithms/{zip_name}")
            )

        self.stdout.write(
            f"Done: repaired={repaired} already_ok={skipped_ok} "
            f"no_bundle_zip={skipped_no_bundle} no_db_row={skipped_no_row} dry_run={dry_run}"
        )
