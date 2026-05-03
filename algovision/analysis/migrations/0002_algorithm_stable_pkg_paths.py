"""Stable algorithms/pkg/<pk>/archive.zip layout + relocate existing archives."""

from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.db import migrations, models

import analysis.models as analysis_models


def relocate_algorithm_archives(apps, schema_editor):
    Algorithm = apps.get_model("analysis", "Algorithm")
    media = Path(settings.MEDIA_ROOT)
    alg_root = media / "algorithms"

    for algo in Algorithm.objects.all():
        old_rel = algo.archive
        if not old_rel:
            continue
        old_rel = str(old_rel).replace("\\", "/")
        prefix = f"algorithms/pkg/{algo.pk}/"
        if old_rel.startswith(prefix):
            continue

        old_abs = media / old_rel
        dest_rel = f"algorithms/pkg/{algo.pk}/archive.zip"
        dest_abs = media / dest_rel

        pkg_dir = alg_root / "pkg" / str(algo.pk)
        pkg_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(old_rel).stem
        legacy_extract = alg_root / stem
        if legacy_extract.is_dir():
            try:
                rel_parts = legacy_extract.relative_to(alg_root).parts
            except ValueError:
                rel_parts = ()
            if rel_parts and rel_parts[0] != "pkg":
                shutil.rmtree(legacy_extract, ignore_errors=True)

        if old_abs.is_file():
            if dest_abs.exists():
                dest_abs.unlink()
            shutil.move(str(old_abs), str(dest_abs))
            algo.archive = dest_rel
            algo.save(update_fields=["archive"])


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="algorithm",
            name="archive",
            field=models.FileField(
                blank=True,
                max_length=512,
                null=True,
                upload_to=analysis_models.algorithm_archive_upload_to,
            ),
        ),
        migrations.RunPython(relocate_algorithm_archives, migrations.RunPython.noop),
    ]
