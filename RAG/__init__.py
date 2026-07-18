"""
Módulo RAG para la ingesta de datos a LlamaCloud.
"""

from .rag import ingest_data, LLAMA_CLOUD_INDEX_NAME

__all__ = [
    "ingest_data",
    "LLAMA_CLOUD_INDEX_NAME",
]
