"""
Herramienta de Retrieval: conecta con la colección de vectores en Qdrant y la
expone como una tool de LangChain lista para registrarse en un agente
(`create_agent`).

Lee desde el MISMO vector store y con el MISMO embedding model que la ingesta
(RAG/rag.py), porque ambos importan la config desde `vector_store.py`. Solo
RECUPERAMOS los chunks relevantes y devolvemos su texto; la síntesis de la
respuesta la hace el LLM del agente (gpt-4.1 vía LangChain). Patrón idiomático
de "RAG como tool".
"""

import os
import sys

from llama_index.core import VectorStoreIndex
from langchain.tools import tool

# vector_store.py vive en la raíz del proyecto.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vector_store import get_vector_store, get_embed_model


def get_index():
    """
    Carga el índice desde la colección de Qdrant (sin reindexar): construye un
    VectorStoreIndex 'en vivo' sobre los vectores ya existentes.
    """
    vector_store = get_vector_store()
    return VectorStoreIndex.from_vector_store(
        vector_store,
        embed_model=get_embed_model(),
    )


def get_retrieval_tool(index, similarity_top_k: int = 5):
    """
    Envuelve el índice de Qdrant como una tool de LangChain.

    Devuelve los fragmentos (chunks) más relevantes para que el agente los use
    como contexto. Es una tool compartida entre todos los leads (no depende del
    lead_id).
    """
    retriever = index.as_retriever(similarity_top_k=similarity_top_k)

    @tool
    def knowledge_base(query: str) -> str:
        """Consulta las políticas y FAQ de la inmobiliaria Alpha State (alquiler en
        Campinas/SP): composición del boleto (alquiler neto, IPTU, SANASA, seguro de
        incendio, gastos bancarios), multas e intereses por atraso, reajuste anual,
        documentación y garantías para alquilar, responsabilidades de mantenimiento y
        cálculo de servicios compartidos. NO cubre el inventario de inmuebles (para eso
        usa buscar_inmuebles). Argumento: 'query' = la pregunta o tema a buscar."""
        nodes = retriever.retrieve(query)
        if not nodes:
            return "No se encontró información relevante en el catálogo."
        return "\n\n---\n\n".join(n.node.get_content() for n in nodes)

    return knowledge_base
