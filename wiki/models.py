from django.db import models
from llm_wiki.settings import MEDIA_DIR
from .enum import Status
from uuid import uuid4

def raw_document_upload_to(instance, filename):
    return f"{instance.workspace.name}/raw/{filename}"

class Workspace(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Document(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    file = models.FileField(upload_to=raw_document_upload_to)
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.file.name

class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    content = models.TextField()
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.id)

class WikiPage(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    chunks = models.ManyToManyField(Chunk, related_name="wiki_pages")
    uuid = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    tags = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
