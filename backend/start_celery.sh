#!/bin/bash

# Start Celery Worker
celery -A myproject worker --loglevel=info --queues=file_processing,cleanup

# Start Celery Beat (scheduled tasks)
celery -A myproject beat --loglevel=info

# Start Celery Flower (monitoring interface)
celery -A myproject flower --port=5555 