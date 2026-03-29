# algovision/celery.py

import os
import ssl
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'algovision.settings')

app = Celery('algovision')

# We use the Django settings file for Celery configuration
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks.py in all apps
app.autodiscover_tasks()
