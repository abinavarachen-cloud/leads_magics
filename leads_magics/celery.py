from __future__ import absolute_import, unicode_literals
import os
import ssl
from celery import Celery
from celery.schedules import crontab


# Completely disable SSL verification for development
ssl._create_default_https_context = ssl._create_unverified_context

# Also set environment variables
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

# Set default settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leads_magics.settings')

app = Celery('leads_magics')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
    
    
# Configure Celery Beat schedule
app.conf.beat_schedule = {
    # Check for scheduled campaigns every minute
    'check-scheduled-campaigns-every-minute': {
        'task': 'api.tasks.check_and_send_scheduled_campaigns',
        'schedule': crontab(minute='*/1'),  # Every minute
        'options': {
            'expires': 30.0,  # Expire after 30 seconds
        },
    },
    # Generate preview recipients for campaigns scheduled in the next hour
    'pre-generate-recipients': {
        'task': 'api.tasks.pregenerate_recipients_for_upcoming_campaigns',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    # Clean up old data daily at midnight
    'cleanup-old-data-daily': {
        'task': 'api.tasks.cleanup_old_campaigns',
        'schedule': crontab(hour=0, minute=0),  # Midnight daily
    },
}

# Optional: Additional periodic tasks
app.conf.beat_schedule.update({
    # Health check every 10 minutes
    'health-check': {
        'task': 'api.tasks.health_check',
        'schedule': crontab(minute='*/10'),
    },
})

app.conf.timezone = 'UTC'
app.conf.enable_utc = True