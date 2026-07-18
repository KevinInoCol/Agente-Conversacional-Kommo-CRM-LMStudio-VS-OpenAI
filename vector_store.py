"""
Configuración COMPARTIDA del vector store (Qdrant) — fuente única de verdad
para la ingesta (RAG/rag.py) y el retrieval (tools/retrieval.py).

Está escrito contra la abstracción VectorStore de LlamaIndex: para migrar a
pgvector / Pinecone / etc. solo hay que reescribir `get_vector_store()` y
`get_embed_model()`; el pipeline de ingesta y la tool de retrieval no cambian.

El embedding model y la colección DEBEN ser idénticos en ingesta y consulta.
Por eso viven aquí y ambos módulos los importan desde el mismo lugar (evita el
clásico bug de "ingesto en un índice y consulto en otro").

Conexión vía .env:
- QDRANT_URL        → si está, usa modo remoto/cloud (ej: https://xxx.cloud.qdrant.io:6333)
- QDRANT_API_KEY    → API key de Qdrant Cloud (opcional)
- QDRANT_HOST       → default "localhost"  (Qdrant local en Docker)
- QDRANT_PORT       → default 6333
- QDRANT_COLLECTION → default "productos_de_salud_kommo_crm"
"""

import os
from urllib.parse import urlparse

from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

# Debe coincidir entre ingesta y consulta.
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
DEFAULT_COLLECTION = "productos_de_salud_kommo_crm"


def get_embed_model() -> OpenAIEmbedding:
    """Modelo de embeddings compartido (mismo en ingesta y retrieval)."""
    return OpenAIEmbedding(model=EMBED_MODEL, dimensions=EMBED_DIM)


def get_collection_name() -> str:
    """Nombre de la colección Qdrant. Parametrizable por proyecto/cliente."""
    return os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION)


def get_qdrant_client() -> QdrantClient:
    """
    Construye el cliente Qdrant. Si QDRANT_URL está definida usa modo remoto
    (Qdrant Cloud, o tu Qdrant en DigitalOcean/Easypanel); si no, se conecta a
    un Qdrant local (Docker en localhost:6333 por defecto).

    OJO con Qdrant detrás de un reverse proxy (Easypanel/Traefik, Nginx, etc.):
    el servicio se publica por el puerto del dominio (443 en https), NO por el
    6333 interno. Y `qdrant-client`, si recibe una URL https SIN puerto, asume
    6333 y la conexión falla. Por eso, si la URL no trae puerto, forzamos 443
    (https) / 80 (http). También usamos REST (prefer_grpc=False) porque el
    puerto gRPC (6334) normalmente NO está expuesto a través del proxy.
    """
    url = os.getenv("QDRANT_URL")
    if url:
        parsed = urlparse(url)
        kwargs = {
            "url": url,
            "api_key": os.getenv("QDRANT_API_KEY") or None,
            "prefer_grpc": False,  # el proxy solo expone HTTP/REST, no gRPC
            "timeout": int(os.getenv("QDRANT_TIMEOUT", "60")),
        }
        # Si la URL no incluye puerto explícito, evitamos el default 6333.
        if parsed.port is None:
            kwargs["port"] = 443 if parsed.scheme == "https" else 80
        # Easypanel a veces sirve bajo un sub-path (ej: dominio.com/qdrant).
        prefix = os.getenv("QDRANT_PREFIX")
        if prefix:
            kwargs["prefix"] = prefix
        return QdrantClient(**kwargs)

    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)


def get_vector_store(client: QdrantClient | None = None) -> QdrantVectorStore:
    """Devuelve el QdrantVectorStore (abstracción VectorStore de LlamaIndex)."""
    client = client or get_qdrant_client()
    return QdrantVectorStore(
        client=client,
        collection_name=get_collection_name(),
    )


# ──────────────────────────────────────────────
# Diagnóstico de conexión:  python vector_store.py
# ──────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    url = os.getenv("QDRANT_URL")
    if url:
        parsed = urlparse(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        print(f"🔌 Modo remoto → {parsed.scheme}://{parsed.hostname}:{port}"
              f"{os.getenv('QDRANT_PREFIX', '')}")
        print(f"   API key: {'sí' if os.getenv('QDRANT_API_KEY') else 'NO (¿requerida?)'}")
    else:
        print(f"🔌 Modo local → {os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}")

    try:
        client = get_qdrant_client()
        collections = [c.name for c in client.get_collections().collections]
        print("✅ Conexión OK con Qdrant.")
        print(f"   Colecciones existentes: {collections or '(ninguna)'}")
        target = get_collection_name()
        print(f"   Colección objetivo ('{target}'): "
              f"{'EXISTE' if target in collections else 'no existe aún (se creará al indexar)'}")
    except Exception as e:
        print("❌ No se pudo conectar a Qdrant.")
        print(f"   Detalle: {type(e).__name__}: {e}")
        print("\n   Checklist Easypanel/DigitalOcean:")
        print("   1. QDRANT_URL debe ser el dominio público https (ej: https://qdrant.tudominio.com)")
        print("   2. Si pones el puerto, usa :443 (NO :6333). Sin puerto, el código ya asume 443.")
        print("   3. Define QDRANT_API_KEY (Easypanel expuesto a internet debería tener API key).")
        print("   4. Verifica desde tu máquina:  curl -H 'api-key: TU_KEY' https://qdrant.tudominio.com/collections")
