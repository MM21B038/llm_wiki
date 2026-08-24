from django_rq import get_connection
from redis.lock import Lock

from wiki.enum import Status
from wiki.models import Chunk, Document
from wiki.services.agent import wiki_agent


def process_chunk(chunk_id: int) -> None:
    chunk = Chunk.objects.select_related("document__workspace").get(id=chunk_id)
    workspace_id = chunk.document.workspace_id
    conn = get_connection("wiki")
    lock = Lock(
        conn,
        f"wiki-workspace:{workspace_id}",
        timeout=1800,
        blocking_timeout=1800,
    )
    try:
        with lock:
            wiki_agent(workspace_id, chunk)
    except Exception:
        Chunk.objects.filter(id=chunk_id).update(status=Status.FAILED)
        Document.objects.filter(id=chunk.document_id).update(status=Status.FAILED)
        raise

    unfinished = Chunk.objects.filter(
        document_id=chunk.document_id,
        status__in=[Status.PENDING, Status.QUEUED, Status.PROCESSING],
    ).exists()
    if not unfinished:
        Document.objects.filter(id=chunk.document_id).update(status=Status.COMPLETED)