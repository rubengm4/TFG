import os

from django.db import migrations, models


def backfill_display_name(apps, schema_editor):
    File = apps.get_model("analysis", "File")
    for row in File.objects.iterator():
        if row.display_name:
            continue
        path = row.file
        if not path:
            continue
        base = os.path.basename(str(path))[:255]
        if base:
            row.display_name = base
            row.save(update_fields=["display_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0004_alter_algorithm_input_is_dir"),
    ]

    operations = [
        migrations.AddField(
            model_name="file",
            name="display_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Nombre mostrado al usuario; el fichero en disco usa un nombre opaco.",
                max_length=255,
            ),
        ),
        migrations.RunPython(backfill_display_name, migrations.RunPython.noop),
    ]
