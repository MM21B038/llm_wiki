from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
import tiktoken
from wiki.models import Document, Chunk
from wiki.serializers import DocumentSerializer
from pathlib import Path
from typing import List
from wiki.enum import Status
from django_rq import get_queue
from wiki.tasks import process_chunk

CHUNK_SIZE = 4096
ENCODER = tiktoken.encoding_for_model("gpt-4o-mini")

def make_chunks(document: Document) -> List[str]:
    ext = Path(document.file.name).suffix.lower()
    if ext not in {".txt", ".md"}:
        return []
    content = document.file.read().decode("utf-8")
    tokens = ENCODER.encode(content)
    print(f"Tokens: {len(tokens)} for document: {document.id}")
    chunks = []
    for i in range(0, len(tokens), CHUNK_SIZE):
        chunks.append(ENCODER.decode(tokens[i:i+CHUNK_SIZE]))
    return chunks

def retry_chunks() -> None:
    document = Document.objects.get(status=Status.FAILED)
    if document:
        chunks = Chunk.objects.filter(document=document, status=Status.FAILED)
        if chunks:
            retry_queue = get_queue("wiki_retry")
            for chunk in chunks:
                retry_queue.enqueue(process_chunk, chunk.id, job_timeout=1800)
                chunk.status=Status.QUEUED
                chunk.save()
            document.status = Status.PROCESSING
            document.save()

class DocumentView(GenericAPIView):
    serializer_class = DocumentSerializer
    queryset = Document.objects.all()
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        document = serializer.instance
        chunks = make_chunks(document)
        if chunks:
            queue = get_queue("wiki")
            for chunk in chunks:
                chunk = Chunk.objects.create(document=document, content=chunk, status=Status.PENDING)
                queue.enqueue(process_chunk, chunk.id, job_timeout=1800)
                Chunk.objects.filter(id=chunk.id).update(status=Status.QUEUED)
            Document.objects.filter(id=document.id).update(status=Status.PROCESSING)
            retry_chunks()
            return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.data, status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, file_id: str):
        document = get_object_or_404(
            Document,
            id=file_id,
        )
        document.file.delete(save=False)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)