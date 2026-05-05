from django.contrib.auth.models import User
from django.db import models
import os


def algorithm_archive_upload_to(instance: "Algorithm", filename: str) -> str:
    """One ZIP per algorithm under ``algorithms/pkg/<pk>/archive.zip``.

    Callers that assign ``archive`` before the row has a primary key must save the
    instance first with ``archive`` empty (see bootstrap / sync commands).
    """
    if instance.pk is None:
        raise ValueError(
            "algorithm_archive_upload_to requires Algorithm.pk; save the row before "
            "assigning the ZIP file."
        )
    return f"algorithms/pkg/{instance.pk}/archive.zip"

# Model: Project


class Project(models.Model):
    title = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    start_date = models.DateField()

    def __str__(self):
        return self.title

# Model: UserProject (many-to-many relationship)


class FileType(models.Model):
    code = models.CharField(max_length=50, unique=True)  # ej: 'csv', 'image'
    name = models.CharField(max_length=100)  # ej: 'CSV', 'Image'

    def __str__(self):
        return self.name


class UserProject(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateField()

    class Meta:
        unique_together = ('project', 'user')

# Model: File


def user_directory_path(instance: 'File', filename: str):
    return f'uploads/{instance.user.id}/{filename}'


class File(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    file = models.FileField(
        upload_to=user_directory_path, null=True, blank=True)
    type = models.ForeignKey(FileType, on_delete=models.CASCADE)
    upload_date = models.DateTimeField()

    def filename(self):
        return os.path.basename(self.file.name)

# Model: Algorithm


class Algorithm(models.Model):
    name = models.CharField(max_length=255)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True)
    version = models.CharField(max_length=50)
    description = models.TextField()
    archive = models.FileField(
        upload_to=algorithm_archive_upload_to,
        max_length=512,
        blank=True,
        null=True,
    )
    entrypoint = models.CharField(
        max_length=255, help_text="Archivo principal a ejecutar, por ejemplo: main.py")
    supported_types = models.ManyToManyField(FileType, blank=True)
    requires_two_files = models.BooleanField(default=False)
    input_is_dir = models.BooleanField(
        default=False,
        verbose_name="Imagen: pasar carpeta al script",
        help_text=(
            "Si está marcado, para entradas de tipo imagen el worker pasa la ruta de una carpeta "
            "temporal que contiene el fichero (útil si el script hace os.listdir sobre el argumento). "
            "Si no, se pasa la ruta del fichero de imagen."
        ),
    )

    def __str__(self):
        return self.name


# Model: Execution


class Execution(models.Model):
    EXECUTION_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('FINISHED', 'Finished'),
        ('FAILED', 'Failed'),
    ]

    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    algorithm = models.ForeignKey(
        Algorithm, null=True, on_delete=models.SET_NULL)
    file = models.ForeignKey(File, null=True, on_delete=models.SET_NULL)
    secondary_file = models.ForeignKey(
        File, on_delete=models.SET_NULL, null=True, blank=True, related_name='secondary_execs')
    execution_date = models.DateTimeField()
    status = models.CharField(max_length=50, choices=EXECUTION_STATUS_CHOICES)
    snapshot_file_name = models.CharField(
        max_length=255, default="PLACEHOLDER")
    snapshot_alg_name = models.CharField(
        max_length=255, default="PLACEHOLDER")

    def __str__(self):
        return f"Execution {self.pk} - {self.status}"

# Model: Output


def output_directory_path(instance: 'File', filename):
    return f'outputs/{instance.user.id}/{filename}'


class Output(models.Model):
    execution = models.ForeignKey(Execution, on_delete=models.CASCADE)
    file = models.FileField(
        upload_to=output_directory_path, null=True, blank=True)
    output_date = models.DateTimeField()

    def __str__(self):
        return f"Output for Execution {self.execution.pk}"
