from rest_framework import serializers
from wiki.models import Workspace, Document


class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ["id", "name", "description"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "name": {"required": True},
            "description": {"required": False, "allow_blank": True, "allow_null": True},
        }


class DocumentSerializer(serializers.ModelSerializer):
    workspace = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Workspace.objects.all(),
    )
    class Meta:
        model = Document
        fields = ["id", "workspace", "file", "status"]
        read_only_fields = ["id", "status"]