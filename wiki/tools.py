from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union
from uuid import UUID
import re

import difflib
import frontmatter
from django.conf import settings
from langchain_core.tools import tool
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from wiki.models import Workspace
from wiki.schemas import (
    DeleteWikiPageRequest,
    DeleteWikiPageResponse,
    InsertBodyRequest,
    InsertWikiPageDataRequest,
    InsertWikiPageDataResponse,
    Metadata,
    MetadataRequest,
    MetadataResponse,
    ReadWikiPageRequest,
    ReadWikiPageResponse,
    Update,
    UpdateWikiPageMetadataRequest,
    UpdateWikiPageMetadataResponse,
    UpdateWikiPageRequest,
    UpdateWikiPageResponse,
    WikiPage,
)

from composer import Vector
import numpy as np
import os
from dotenv import load_dotenv
load_dotenv()

def add_line_numbers(text: str, width: int = 5) -> str:
    """
    Add stable line numbers to Markdown text.

    Example:
        # Title
        Hello

    becomes:
        00001 | # Title
        00002 | Hello
    """
    lines = text.splitlines()
    return "\n".join(
        f"{i:0{width}d} | {line}"
        for i, line in enumerate(lines, start=1)
    )


def check_workspace_exists(workspace_id: int) -> bool:
    return Workspace.objects.filter(id=workspace_id).exists()


def check_document_exists(path: Path) -> bool:
    return path.exists()


def apply_updates(body: str, start_line: int, end_line: int, new_content: str) -> str:
    lines = body.splitlines(keepends=True)
    start = start_line - 1
    end = end_line
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"
    return "".join(lines[:start] + [new_content] + lines[end:])


def apply_insert(body: str, insert_index: int, content: str) -> str:
    lines = body.splitlines(keepends=True)
    lines.insert(insert_index, content)
    return "".join(lines)


def _workspace_wiki_dir(workspace_id: int) -> Union[Path, str]:
    if not check_workspace_exists(workspace_id):
        return "Workspace not found, please check the workspace ID and try again."
    workspace = Workspace.objects.get(id=workspace_id)
    return settings.MEDIA_DIR / workspace.name / "wiki"


def _wiki_page_path(workspace_id: int, wiki_page_id: UUID) -> Union[Path, str]:
    wiki_dir = _workspace_wiki_dir(workspace_id)
    if isinstance(wiki_dir, str):
        return wiki_dir
    path = wiki_dir / f"{wiki_page_id}.md"
    if not check_document_exists(path):
        return "Wiki page not found, please check the wiki page ID and try again."
    return path


def _metadata_from_post(data: frontmatter.Post) -> Metadata:
    return Metadata.model_validate(data.metadata)


def _metadata_to_dict(metadata: Metadata) -> dict:
    payload = metadata.model_dump(mode="json")
    payload["id"] = str(metadata.id)
    return payload


def _dump_post(path: Path, data: frontmatter.Post) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        frontmatter.dump(data, f)


def _touch_updated_at(data: frontmatter.Post) -> None:
    data.metadata["updated_at"] = datetime.now().isoformat()


def _unified_diff(old_content: str, new_content: str, filename: str) -> str:
    return "".join(
        difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=filename,
            tofile=filename,
        )
    )


def _dump_result(model: BaseModel) -> str:
    return model.model_dump_json()

vec = Vector(
    model=os.getenv("EMB"),
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY"),
)

_TOKEN = re.compile(r"[a-z0-9]+")
def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())

@tool(
    args_schema=MetadataRequest,
    description="Search for most relevant wiki pages in the workspace respective to the query",
)
def search_relevant_wiki_pages(workspace_id: int, query: str, top_k: int = 10, bm25_weight: float = 0.3, semantic_weight: float = 0.7) -> str:
    print(f"Searching for relevant wiki pages for workspace {workspace_id} with query: {query}, top_k: {top_k}, bm25_weight: {bm25_weight}, semantic_weight: {semantic_weight}")
    wiki_dir = _workspace_wiki_dir(workspace_id)
    if isinstance(wiki_dir, str):
        return wiki_dir
    if not check_document_exists(wiki_dir):
        return "No wiki pages found in the workspace, please create a new wiki page first."
    if query is None or query.strip() == "":
        return "Query is required, please provide a valid query."
    results = []
    texts = []
    for file in wiki_dir.glob("*.md"):
        with open(file, "r") as f:
            data = frontmatter.load(f)
        metadata = _metadata_from_post(data)
        results.append(metadata)
        texts.append(
            " ".join([metadata.title, metadata.description, " ".join(metadata.tags)])
        )

    if not results:
        return _dump_result(MetadataResponse(wikis_metadata=[]))
    
    corpus = [_tokenize(text) for text in texts]
    query_tokens = _tokenize(query)
    bm25 = BM25Okapi(corpus)
    lexical_scores = bm25.get_scores(query_tokens)


    doc_embeddings = vec.vector(texts)
    query_embedding = vec.vector(query)

    doc_norm = np.linalg.norm(doc_embeddings, axis=1, keepdims=True)
    query_norm = np.linalg.norm(query_embedding)
    semantic_scores = (doc_embeddings @ query_embedding) / (doc_norm.ravel() * query_norm + 1e-12)

    hybrid_scores = (lexical_scores * bm25_weight + semantic_scores * semantic_weight) / (bm25_weight + semantic_weight)

    top_indices = np.argpartition(hybrid_scores, -top_k)[-top_k:]
    print(f"Top indices: {top_indices} for query: {query}")
    top_results = [results[i] for i in top_indices]
    return _dump_result(MetadataResponse(wikis_metadata=top_results))

@tool(
    args_schema=WikiPage,
    description="Create a new wiki page in the workspace with the given metadata and optional initial body",
)
def create_wiki_page(workspace_id: int, metadata: Metadata, body: Optional[str] = None) -> str:
    print(f"Creating wiki page for workspace {workspace_id} with metadata: {metadata}")
    wiki_dir = _workspace_wiki_dir(workspace_id)
    if isinstance(wiki_dir, str):
        return wiki_dir

    path = wiki_dir / f"{metadata.id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(body or "", **_metadata_to_dict(metadata))
    _dump_post(path, post)
    return f"Wiki page created successfully with wiki page ID: {metadata.id}"


# @tool(
#     args_schema=InsertBodyRequest,
#     description="Replace the entire body of the wiki page with the given body",
# )
# def replace_wiki_page_body(workspace_id: int, wiki_page_id: UUID, body: str) -> str:
#     print(f"Replacing wiki page body for workspace {workspace_id} with wiki page ID: {wiki_page_id}")
#     path = _wiki_page_path(workspace_id, wiki_page_id)
#     if isinstance(path, str):
#         return path
#     with open(path, "r") as f:
#         data = frontmatter.load(f)
#     data.content = body
#     _touch_updated_at(data)
#     _dump_post(path, data)
#     return f"Body replaced successfully with wiki page ID: {wiki_page_id}"


@tool(
    args_schema=ReadWikiPageRequest,
    description="Read the full content of the wiki page with the given wiki page ID",
)
def read_wiki_page(workspace_id: int, wiki_page_id: UUID) -> str:
    print(f"Reading wiki page for workspace {workspace_id} with wiki page ID: {wiki_page_id}")
    path = _wiki_page_path(workspace_id, wiki_page_id)
    if isinstance(path, str):
        return path
    with open(path, "r") as f:
        data = frontmatter.load(f)
    return _dump_result(
        ReadWikiPageResponse(
            workspace_id=workspace_id,
            wiki_page_id=wiki_page_id,
            metadata=_metadata_from_post(data),
            body=add_line_numbers(data.content),
        )
    )


@tool(
    args_schema=UpdateWikiPageRequest,
    description="Update a character span of the wiki page body with the given new content and start and end line numbers",
)
def update_wiki_page_content(workspace_id: int, wiki_page_id: UUID, update: Update) -> str:
    print(f"Updating wiki page body for workspace {workspace_id} with wiki page ID: {wiki_page_id}")
    path = _wiki_page_path(workspace_id, wiki_page_id)
    if isinstance(path, str):
        return path
    with open(path, "r") as f:
        data = frontmatter.load(f)
    old_content = data.content
    print(f"Update: {update.start}, {update.end}, {update.new_content}")
    new_content = apply_updates(old_content, [update])
    data.content = new_content
    _touch_updated_at(data)
    _dump_post(path, data)
    applied_updates=_unified_diff(old_content, new_content, f"{wiki_page_id}.md")
    print(f"Applied updates: {applied_updates}")
    return _dump_result(
        UpdateWikiPageResponse(
            workspace_id=workspace_id,
            wiki_page_id=wiki_page_id,
            applied_updates=_unified_diff(old_content, new_content, f"{wiki_page_id}.md"),
        )
    )


@tool(
    args_schema=UpdateWikiPageMetadataRequest,
    description="Update the metadata of the wiki page with the given metadata",
)
def update_wiki_page_metadata(
    workspace_id: int,
    wiki_page_id: UUID,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> str:
    print(f"Inserting new content for workspace {workspace_id} with wiki page ID: {wiki_page_id} and insert index: {insert_index}")
    path = _wiki_page_path(workspace_id, wiki_page_id)
    if isinstance(path, str):
        return path
    with open(path, "r") as f:
        data = frontmatter.load(f)
    if title:
        data.metadata["title"] = title
    if description:
        data.metadata["description"] = description
    if tags is not None:
        data.metadata["tags"] = tags
    _touch_updated_at(data)
    _dump_post(path, data)
    return _dump_result(
        UpdateWikiPageMetadataResponse(
            workspace_id=workspace_id,
            wiki_page_id=wiki_page_id,
            updated_metadata=_metadata_from_post(data),
        )
    )


@tool(
    args_schema=InsertWikiPageDataRequest,
    description="Insert the given content at the given line number in the wiki page body",
)
def insert_new_content(
    workspace_id: int,
    wiki_page_id: UUID,
    insert_index: int,
    content: str,
) -> str:
    print(f"Deleting wiki page for workspace {workspace_id} with wiki page ID: {wiki_page_id}")
    path = _wiki_page_path(workspace_id, wiki_page_id)
    if isinstance(path, str):
        return path
    with open(path, "r") as f:
        data = frontmatter.load(f)
    old_content = data.content
    new_content = apply_insert(old_content, insert_index, content)
    data.content = new_content
    _touch_updated_at(data)
    _dump_post(path, data)
    return _dump_result(
        InsertWikiPageDataResponse(
            workspace_id=workspace_id,
            wiki_page_id=wiki_page_id,
            applied_updates=_unified_diff(old_content, new_content, f"{wiki_page_id}.md"),
        )
    )


@tool(
    args_schema=DeleteWikiPageRequest,
    description="Delete the wiki page with the given wiki page ID",
)
def delete_wiki_page(workspace_id: int, wiki_page_id: UUID) -> str:
    print(f"Deleting wiki page for workspace {workspace_id} with wiki page ID: {wiki_page_id}")
    path = _wiki_page_path(workspace_id, wiki_page_id)
    if isinstance(path, str):
        return path
    path.unlink()
    return _dump_result(
        DeleteWikiPageResponse(
            workspace_id=workspace_id,
            wiki_page_id=wiki_page_id,
            message="Wiki page deleted successfully",
        )
    )


tools = [
    search_relevant_wiki_pages,
    create_wiki_page,
    # replace_wiki_page_body,
    read_wiki_page,
    update_wiki_page_content,
    update_wiki_page_metadata,
    insert_new_content,
    delete_wiki_page,
]
