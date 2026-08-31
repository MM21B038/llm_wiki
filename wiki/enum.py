from django.db import models

class Status(models.TextChoices):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    QUEUED = 'queued'
