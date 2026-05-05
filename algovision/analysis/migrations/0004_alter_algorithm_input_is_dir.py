from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0003_algorithm_input_is_dir"),
    ]

    operations = [
        migrations.AlterField(
            model_name="algorithm",
            name="input_is_dir",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Si está activado y el usuario sube una imagen, Celery entrega al script la ruta de "
                    "una carpeta temporal que contiene ese archivo (útil cuando el script espera un "
                    "directorio y usa os.listdir). Si está desactivado, se entrega la ruta del archivo "
                    "de imagen. Para vídeo y CSV no aplica: siempre se pasa la ruta del archivo."
                ),
                verbose_name="Pasar carpeta para imágenes",
            ),
        ),
    ]
