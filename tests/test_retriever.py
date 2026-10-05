# Tests for the document ingestion and retrieval system:
# - Create a temporary Milvus database and populate it with test documents.
# - Verify that relevant public documents can be retrieved.
# - Verify that private documents are never returned by the retriever.

import pytest

from src.ingest import ingest
from src.retriever import get_retriever


# Create and populate one temporary Milvus database for all tests in this module.
@pytest.fixture(scope="module")
def uri(tmp_path_factory):
    # Create a temporary database path for the test.
    path = str(tmp_path_factory.mktemp("milvus") / "test.db")

    # Ingest the static documents into the temporary Milvus database.
    ingest(uri=path)

    # Return the database URI so tests can use it.
    return path


# Verify that a location-related question retrieves the location document.
def test_location_question_finds_location_doc(uri):
    docs = get_retriever(k=4, uri=uri).invoke("where is the parking located?")

    # Check that location.md is among the retrieved documents.
    assert "location.md" in {d.metadata["source"] for d in docs}


# Verify that the retriever never returns private documents.
def test_private_chunks_are_never_returned(uri):
    retriever = get_retriever(k=5, uri=uri)

    # Test several queries that could potentially target private information.
    for q in ["customer John Smith phone number", "admin override code", "VIP list"]:
        # Every returned document must have public sensitivity.
        assert all(
            d.metadata["sensitivity"] == "public"
            for d in retriever.invoke(q))