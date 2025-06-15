from django.contrib.auth.models import User
from django.db import models
import os

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
    role = models.CharField(max_length=100)

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
    archive = models.FileField(upload_to='algorithms/')
    entrypoint = models.CharField(
        max_length=255, help_text="Archivo principal a ejecutar, por ejemplo: main.py")
    supported_types = models.ManyToManyField(FileType, blank=True)

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
    execution_date = models.DateTimeField()
    status = models.CharField(max_length=50, choices=EXECUTION_STATUS_CHOICES)

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
