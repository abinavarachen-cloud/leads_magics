# leads_magics/celery.py
import os
from celery import Celery
from django.conf import settings  # Add this import

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leads_magics.settings')

app = Celery('leads_magics')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
# app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)  # Remove this line
app.autodiscover_tasks()  # Use this simplified version

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')