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
import threading
from wiki.services.agent import wiki_agent
from wiki.enum import Status

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
            for chunk in chunks:
                chunk = Chunk.objects.create(document=document, content=chunk, status=Status.PENDING)
                thread = threading.Thread(target=wiki_agent, args=(document.workspace.id, chunk))
                thread.start()
            document.status = Status.PROCESSING
            document.save()
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
        Chunk.objects.filter(document=document).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)