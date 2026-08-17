from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Metadata(BaseModel):
    id: UUID = Field(
        default_factory=uuid4,
        description="The ID of the wiki page, assigned automatically when the wiki page is created",
    )
    title: str = Field(..., description="The title of the wiki page")
    description: str = Field(..., description="The description of the wiki page")
    tags: List[str] = Field(..., description="The tags of the wiki page")
    created_at: Optional[str] = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="The creation date of the wiki page, assigned automatically when the wiki page is created",
    )
    updated_at: Optional[str] = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="The last update date of the wiki page, assigned automatically when the wiki page is created or updated",
    )


class MetadataRequest(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    query: str = Field(..., description="The query to search for")
    top_k: int = Field(default=10, description="The number of results to return")
    bm25_weight: float = Field(default=0.3, description="The weight of the BM25 score")
    semantic_weight: float = Field(default=0.7, description="The weight of the semantic score")


class MetadataResponse(BaseModel):
    wikis_metadata: List[Metadata] = Field(..., description="The list of wiki pages metadata")


class WikiPage(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    metadata: Metadata = Field(..., description="The metadata of the wiki page")
    body: Optional[str] = Field(default=None, description="The body of the wiki page")


class InsertBodyRequest(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")
    body: str = Field(..., description="The full replacement body of the wiki page")


class ReadWikiPageRequest(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")


class ReadWikiPageResponse(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")
    metadata: Metadata = Field(..., description="The metadata of the wiki page")
    body: Optional[str] = Field(default=None, description="The body of the wiki page")


class Update(BaseModel):
    start: int = Field(..., description="The start character index of the update (inclusive)")
    end: int = Field(..., description="The end character index of the update (exclusive)")
    new_content: str = Field(
        ...,
        description="The new content to replace the span from start to end in the wiki page body",
    )


class UpdateWikiPageRequest(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")
    update: Update = Field(..., description="The span replacement to apply to the wiki page body")


class UpdateWikiPageResponse(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")
    applied_updates: str = Field(..., description="The unified diff of the applied body update")


class UpdateWikiPageMetadataRequest(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")
    title: Optional[str] = Field(default=None, description="The updated title of the wiki page")
    description: Optional[str] = Field(
        default=None, description="The updated description of the wiki page"
    )
    tags: Optional[List[str]] = Field(default=None, description="The updated tags of the wiki page")


class UpdateWikiPageMetadataResponse(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")
    updated_metadata: Metadata = Field(..., description="The updated metadata")


class InsertWikiPageDataRequest(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")
    insert_index: int = Field(..., description="The character index at which to insert the new content")
    content: str = Field(..., description="The content to insert at the insert index")


class InsertWikiPageDataResponse(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")
    applied_updates: str = Field(..., description="The unified diff of the applied insert")


class DeleteWikiPageRequest(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")


class DeleteWikiPageResponse(BaseModel):
    workspace_id: int = Field(..., description="The ID of the workspace")
    wiki_page_id: UUID = Field(..., description="The ID of the wiki page")
    message: str = Field(..., description="The message of the deletion")
