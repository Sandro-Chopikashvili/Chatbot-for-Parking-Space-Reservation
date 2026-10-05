# Set up the Milvus vector store and create a retriever for searching stored documents.
# Only documents marked as "public" are retrieved, with a configurable number of results.

from langchain_milvus import Milvus
from src.ingest import MILVUS_URI, get_embeddings


def get_store(uri: str = MILVUS_URI):
    return Milvus(embedding_function=get_embeddings(), connection_args={"uri": uri})


def get_retriever(k: int = 4, uri: str = MILVUS_URI):
    return get_store(uri).as_retriever(
        search_kwargs={"k": k, "expr": 'sensitivity == "public"'}
    )