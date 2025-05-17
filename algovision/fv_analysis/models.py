from django.contrib.auth.models import User
from django.db import models

# Model: Project


class Project(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    start_date = models.DateField()

    def __str__(self):
        return self.title

# Model: UserProject (many-to-many relationship)


class UserProject(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateField()
    role = models.CharField(max_length=100)

    class Meta:
        unique_together = ('project', 'user')

# Model: File


class File(models.Model):
    FILE_TYPE_CHOICES = [
        ('csv', 'CSV'),
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=FILE_TYPE_CHOICES)
    upload_date = models.DateField()

    def __str__(self):
        return self.name

# Model: Algorithm


class Algorithm(models.Model):
    name = models.CharField(max_length=255)
    version = models.CharField(max_length=50)
    description = models.TextField()

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
    execution_date = models.DateField()
    status = models.CharField(max_length=50, choices=EXECUTION_STATUS_CHOICES)

    def __str__(self):
        return f"Execution {self.id} - {self.status}"

# Model: Report


class Report(models.Model):
    execution = models.ForeignKey(Execution, on_delete=models.CASCADE)
    path = models.TextField()
    report_date = models.DateField()

    def __str__(self):
        return f"Report for Execution {self.execution.id}"
