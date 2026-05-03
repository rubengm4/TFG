"""Verify Algorithm rows against files on the default storage (e.g. MEDIA_ROOT)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from analysis.models import Algorithm


def _bundled_algorithms_dir() -> Path:
    return Path(settings.BASE_DIR) / "analysis" / "seeds" / "bundled_algorithms"


class Command(BaseCommand):
    help = (
        "List each Algorithm and whether its archive exists on disk. "
        "Use --zip-probe to validate ZIP headers. "
        "Use --list-bundle to show ZIPs under bundled_algorithms (same names as algorithms_manifest.yaml)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--zip-probe",
            action="store_true",
            help="Open each archive path with zipfile (fails for corrupt/non-zip files).",
        )
        parser.add_argument(
            "--list-bundle",
            action="store_true",
            help="List *.zip files in analysis/seeds/bundled_algorithms (for comparison with manifest).",
        )

    def handle(self, *args, **options):
        zip_probe: bool = options["zip_probe"]
        list_bundle: bool = options["list_bundle"]
        bundled_dir = _bundled_algorithms_dir()
        if list_bundle:
            self.stdout.write(f"bundled_algorithms dir={bundled_dir}")
            if bundled_dir.is_dir():
                zips = sorted(bundled_dir.glob("*.zip"))
                if not zips:
                    self.stdout.write(
                        self.style.WARNING("  (no .zip files — may be gitignored / use sync from CI)")
                    )
                for p in zips:
                    self.stdout.write(f"  bundle: {p.name}")
            else:
                self.stdout.write(self.style.WARNING("  directory missing"))
            self.stdout.write("")

        qs = Algorithm.objects.all().order_by("project_id", "name", "version")
        total_rows = qs.count()
        self.stdout.write(
            f"MEDIA_ROOT={settings.MEDIA_ROOT} ({total_rows} algorithm row(s))"
        )
        missing = 0
        bad_zip = 0
        for algo in qs:
            name_field = algo.archive.name if algo.archive else ""
            if not name_field:
                self.stdout.write(
                    self.style.WARNING(f"[{algo.pk}] {algo.name} — sin archivo en FileField")
                )
                missing += 1
                continue
            exists = default_storage.exists(name_field)
            path = Path(algo.archive.path) if exists else None
            line = f"[{algo.pk}] {algo.name} ({algo.version}) — {name_field} exists={exists}"
            if not exists:
                self.stdout.write(self.style.ERROR(line))
                missing += 1
                continue
            self.stdout.write(line)
            if zip_probe and path is not None:
                if not path.is_file():
                    self.stdout.write(
                        self.style.ERROR(f"    not a file: {path}")
                    )
                    missing += 1
                    continue
                if not zipfile.is_zipfile(path):
                    self.stdout.write(
                        self.style.WARNING(
                            f"    zip-probe: no es un ZIP válido (o corrupto): {path}"
                        )
                    )
                    bad_zip += 1
                else:
                    self.stdout.write("    zip-probe: OK")
        self.stdout.write(
            f"Summary: missing_or_empty={missing} bad_zip_probe={bad_zip} "
            f"total_rows={total_rows}"
        )
