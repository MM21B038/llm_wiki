from django.contrib import admin
from .models import Workspace, Document, Chunk, WikiPage

# Register your models here.
admin.site.register(Workspace)
admin.site.register(Document)
admin.site.register(Chunk)
admin.site.register(WikiPage)