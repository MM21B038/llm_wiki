from django.urls import path
from wiki.views.workspace import WorkspaceView, WorkspaceDetailView
from wiki.views.document import DocumentView

urlpatterns = [
    path("workspace/", WorkspaceView.as_view()),
    path("workspace/<str:name>/", WorkspaceDetailView.as_view()),
    path("document/", DocumentView.as_view()),
    path("document/<int:file_id>/", DocumentView.as_view()),
]