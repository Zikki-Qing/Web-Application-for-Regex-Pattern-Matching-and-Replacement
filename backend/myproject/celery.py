import os
from celery import Celery

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# Create Celery application
app = Celery('myproject')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks
app.autodiscover_tasks()

# Task routing configuration
app.conf.task_routes = {
    'regex_processor.tasks.process_file_task': {'queue': 'file_processing'},
    'regex_processor.tasks.cleanup_task': {'queue': 'cleanup'},
}

# Task priority
app.conf.task_default_priority = 5
app.conf.task_queue_max_priority = 10

# Monitoring configuration
app.conf.worker_send_task_events = True
app.conf.task_send_sent_event = True

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}') 