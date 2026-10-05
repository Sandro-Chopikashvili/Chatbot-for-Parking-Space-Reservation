# Load static Markdown documents, split them into chunks, 
# generate embeddings, and store them in Milvus for retrieval.

from functools import lru_cache
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Define project and data paths.
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "data" / "static"
MILVUS_URI = str(ROOT / "milvus.db")

# Hugging Face embedding model used to convert text into vectors.
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# Create the embedding model once and reuse it.
@lru_cache(maxsize=1)
def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)

# Load documents, split them into chunks, embed them, and store them in Milvus.
def ingest(chunk_size: int = 300, chunk_overlap: int = 50, uri: str = MILVUS_URI):

    # Load all Markdown files from the static data directory.
    docs = DirectoryLoader(
        str(STATIC_DIR), glob="*.md", loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    ).load()

    # Add metadata to each document for source tracking and privacy handling.
    for d in docs:
        name = Path(d.metadata["source"]).name
        d.metadata["source"] = name  
        d.metadata["sensitivity"] = "private" if name.startswith("private") else "public"

    # Split documents into smaller overlapping chunks for better retrieval.
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    ).split_documents(docs)

    # Convert chunks into embeddings and store them in the Milvus vector database.
    Milvus.from_documents(
        chunks,
        get_embeddings(),
        connection_args={"uri": uri},
        drop_old=True,
    )
    print(f"Ingested {len(chunks)} chunks from {len(docs)} files into {uri}")

# Run the ingestion process when this file is executed directly.
if __name__ == "__main__":
    ingest()