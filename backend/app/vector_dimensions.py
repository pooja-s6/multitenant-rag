"""Stored width of chunk embeddings.

sentence-transformers/all-MiniLM-L6-v2 returns 384 floats. The database column
uses that width. Changing EMBEDDING_DIMENSION without a new migration is rejected
when a document is saved.
"""

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_VECTOR_DIMENSION = 384
