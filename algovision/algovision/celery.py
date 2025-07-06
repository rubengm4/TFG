# algovision/celery.py

import os
import ssl
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'algovision.settings')

app = Celery('algovision')

# Usamos el archivo de configuración de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks.py en todas las apps
app.autodiscover_tasks()
