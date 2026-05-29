from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.services.embedding_service import embeddings

_index = None


def _get_index():
    global _index
    if _index is not None:
        return _index
    settings = get_settings()
    if not settings.pinecone_api_key:
        return None
    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=settings.pinecone_api_key)
        _index = pc.Index(settings.pinecone_index)
        return _index
    except Exception:
        return None


def user_namespace(user_id: str) -> str:
    return f"user_{user_id.replace('-', '')}"


class PineconeService:
    def upsert_chunks(
        self,
        user_id: str,
        vectors: List[Dict[str, Any]],
    ) -> int:
        index = _get_index()
        if not index:
            return 0
        namespace = user_namespace(user_id)
        index.upsert(vectors=vectors, namespace=namespace)
        return len(vectors)

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        index = _get_index()
        if not index:
            return []

        query_vector = embeddings.embed_text(query)
        namespace = user_namespace(user_id)
        filter_dict = {"document_id": document_id} if document_id else None

        results = index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
            filter=filter_dict,
        )

        matches = []
        for match in results.get("matches", []):
            matches.append({
                "id": match.get("id"),
                "score": match.get("score"),
                "content": match.get("metadata", {}).get("content", ""),
                "document_id": match.get("metadata", {}).get("document_id"),
                "filename": match.get("metadata", {}).get("filename", ""),
            })
        return matches

    def delete_document_vectors(self, user_id: str, document_id: str) -> None:
        index = _get_index()
        if not index:
            return
        namespace = user_namespace(user_id)
        try:
            index.delete(filter={"document_id": document_id}, namespace=namespace)
        except Exception:
            pass


pinecone_svc = PineconeService()
