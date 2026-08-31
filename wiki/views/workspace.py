import os
import shutil

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import JSONParser
from wiki.models import Workspace, Document
from wiki.serializers import (
    WorkspaceSerializer,
    DocumentSerializer,
)

class WorkspaceView(GenericAPIView):
    serializer_class = WorkspaceSerializer
    parser_classes = [JSONParser]
    queryset = Workspace.objects.all()

    def get(self, request) -> Response:
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save()
        (settings.MEDIA_ROOT / workspace.name / "raw").mkdir(parents=True, exist_ok=True)
        (settings.MEDIA_ROOT / workspace.name / "wiki").mkdir(parents=True, exist_ok=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request) -> Response:
        name = request.data.get("name")
        workspace = get_object_or_404(self.queryset, name=name)
        if not workspace:
            return Response(message="Workspace not found", status=status.HTTP_404_NOT_FOUND)
        workspace.delete()
        shutil.rmtree(settings.MEDIA_ROOT / workspace.name)
        return Response(status=status.HTTP_204_NO_CONTENT)

class WorkspaceDetailView(GenericAPIView):
    serializer_class = WorkspaceSerializer
    queryset = Workspace.objects.all()
    lookup_field = "name"          # model field
    lookup_url_kwarg = "name"      # matches <str:name> in urls.py

    def get(self, request, name: str) -> Response:
        workspace = self.get_object()
        documents = Document.objects.filter(workspace=workspace)
        return Response({
            "workspace": self.get_serializer(workspace).data,
            "documents": DocumentSerializer(documents, many=True).data,
        })

    def delete(self, request, name: str) -> Response:
        workspace = self.get_object()
        workspace.delete()
        shutil.rmtree(settings.MEDIA_ROOT / workspace.name, ignore_errors=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
