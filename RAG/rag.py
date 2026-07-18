import os
import glob
from dotenv import load_dotenv
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(message)s'
)

logging.getLogger("httpx").setLevel(logging.WARNING)

load_dotenv()

from llama_index.core import (
    SimpleDirectoryReader,
    Settings,
    VectorStoreIndex,
    StorageContext,
)
from llama_index.core.node_parser import SentenceSplitter

# LlamaParse: parser avanzado que entiende estructura (tablas, encabezados,
# columnas) y devuelve Markdown limpio. El paquete cambió de nombre con el
# tiempo, así que intentamos el actual y caemos al antiguo si hace falta.
try:
    from llama_cloud_services import LlamaParse
except ImportError:
    from llama_parse import LlamaParse

# vector_store.py vive en la raíz del proyecto; lo añadimos al path para poder
# importarlo al ejecutar `python RAG/rag.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vector_store import (
    get_qdrant_client,
    get_vector_store,
    get_collection_name,
    get_embed_model,
)

# LlamaParse sigue usando la API key de LlamaCloud (solo para el parsing).
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")


# ==================== PIPELINE RAG ====================
# Dividimos el pipeline en 4 pasos claros:
#   1. Document Loader        → Cargar archivos (PDF, TXT, DOCX, etc.)
#   2. Document Splitting     → Dividir en chunks manejables
#   3. Embedding Process       → Convertir texto a vectores numéricos
#   4. Vector Store            → Indexar vectores en Qdrant
# ======================================================


# --------------- Paso 2: Document Splitting (Chunking) ----------------
# Definimos CÓMO se dividirán los documentos largos en trozos (chunks).
# El LLM tiene un límite de contexto, así que dividimos en párrafos
# significativos con superposición para no perder contexto entre chunks.

Settings.text_splitter = SentenceSplitter(
    chunk_size=512,      # Tamaño de cada chunk en tokens (512 o 1024 son buenos puntos de partida)
    chunk_overlap=50     # Superposición entre chunks consecutivos (~10-15% del chunk_size)
)

logging.info(f"Configurado el divisor de texto: chunk_size={Settings.text_splitter.chunk_size}, chunk_overlap={Settings.text_splitter.chunk_overlap}")


# --------------- Paso 3: Embedding Process ----------------------------
# Modelo que convierte los chunks de texto en vectores numéricos (embeddings).
# Es crucial usar el MISMO modelo tanto para la ingesta como para las consultas.
# "text-embedding-3-small" de OpenAI es eficiente y potente.

# El modelo vive en vector_store.py (fuente única) para garantizar que ingesta
# y consulta usen EXACTAMENTE el mismo embedding.
Settings.embed_model = get_embed_model()

logging.info(f"Configurado el modelo de embeddings: {Settings.embed_model.model_name}")


def ingest_data():
    """
    Ejecuta el pipeline completo de ingesta de datos:
      Paso 1 → Document Loader: Lee los archivos de 'Base_de_Conocimiento'
      Paso 2 → Splitting: Ya configurado globalmente en Settings.text_splitter
      Paso 3 → Embeddings: Ya configurado globalmente en Settings.embed_model
      Paso 4 → Vector Store: Indexa los vectores en Qdrant
    """

    # --------------- Paso 1: Document Loader (LlamaParse) -----------------
    # Antes: SimpleDirectoryReader usaba un parser PDF genérico (extracción
    # plana, se pierde estructura de tablas/columnas).
    # Ahora: LlamaParse parsea los PDFs entendiendo su estructura y devuelve
    # Markdown limpio → mejores chunks y mejores respuestas del agente.

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    knowledge_base_path = os.path.join(project_root, "Base_de_Conocimiento")

    logging.info(f"Buscando documentos en la carpeta '{knowledge_base_path}'...")

    if not os.path.exists(knowledge_base_path):
        logging.error(f"❌ La carpeta '{knowledge_base_path}' no existe.")
        raise FileNotFoundError(f"No se encontró la carpeta: {knowledge_base_path}")

    # --- Versión anterior con el parser básico (comentada) ---
    # documents = SimpleDirectoryReader(knowledge_base_path).load_data()

    # Recolectamos las rutas de los PDFs y los pasamos a LlamaParse.
    pdf_paths = sorted(glob.glob(os.path.join(knowledge_base_path, "*.pdf")))
    if not pdf_paths:
        logging.warning("No se encontraron PDFs para procesar. Finalizando.")
        return None

    parser = LlamaParse(
        api_key=LLAMA_CLOUD_API_KEY,
        result_type="markdown",   # "markdown" preserva encabezados y tablas; "text" da texto plano
        language="es",            # los documentos están en español → mejora el parseo/OCR
        verbose=True,
    )

    logging.info(f"🔎 Parseando {len(pdf_paths)} PDF(s) con LlamaParse...")
    documents = parser.load_data(pdf_paths)

    if not documents:
        logging.warning("No se encontraron documentos para procesar. Finalizando.")
        return None

    logging.info("=" * 80)
    logging.info(f"📄 DOCUMENTOS ENCONTRADOS: {len(documents)}")
    logging.info("=" * 80)
    for i, doc in enumerate(documents, 1):
        doc_name = getattr(doc, 'metadata', {}).get('file_name', f'Documento {i}')
        logging.info(f"  {i}. {doc_name}")
    logging.info("=" * 80)

    # --- Print de la salida de la extracción (para inspeccionar el parseo) ---
    # Muestra el Markdown que produjo LlamaParse por cada documento.
    print("\n" + "#" * 80)
    print("# CONTENIDO PARSEADO POR LlamaParse (revisión de extracción)")
    print("#" * 80)
    for i, doc in enumerate(documents, 1):
        doc_name = getattr(doc, "metadata", {}).get("file_name", f"Documento {i}")
        text = doc.get_content()
        print(f"\n{'=' * 80}")
        print(f"📄 [{i}/{len(documents)}] {doc_name}  ({len(text)} caracteres)")
        print("=" * 80)
        print(text)
    print("\n" + "#" * 80 + "\n")

    # --------------- Paso 4: Vector Store (Qdrant) ------------------------
    # A diferencia de LlamaCloud, aquí el chunking (Paso 2) y los embeddings
    # (Paso 3) SÍ se ejecutan localmente (vía Settings) y los vectores
    # resultantes se indexan en Qdrant. Escrito contra la abstracción
    # VectorStore de LlamaIndex → cambiar de vector DB es cambiar vector_store.py.

    collection = get_collection_name()
    logging.info(f"\n🚀 Indexando {len(documents)} documento(s) en Qdrant (colección '{collection}')...")

    client = get_qdrant_client()

    # Reindex limpio: si la colección ya existe la recreamos, para no acumular
    # duplicados al reejecutar la ingesta (este script es un 'full reindex').
    existing = [c.name for c in client.get_collections().collections]
    if collection in existing:
        logging.info(f"♻️  La colección '{collection}' ya existe → se recrea para un reindex limpio.")
        client.delete_collection(collection)

    vector_store = get_vector_store(client)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        transformations=[Settings.text_splitter],  # Paso 2 aplicado de verdad
        embed_model=Settings.embed_model,           # Paso 3 aplicado de verdad
        show_progress=True,
    )

    logging.info("\n" + "=" * 80)
    logging.info("✅ PROCESO COMPLETADO EXITOSAMENTE")
    logging.info("=" * 80)
    logging.info(f"📊 Resumen:")
    logging.info(f"   • Documentos procesados: {len(documents)}")
    logging.info(f"   • Colección Qdrant: '{collection}'")
    logging.info("=" * 80)

    return index


if __name__ == "__main__":
    try:
        index = ingest_data()
        if index:
            print("\n" + "=" * 80)
            print("✅ PROCESO COMPLETADO EXITOSAMENTE")
            print("=" * 80)
            print(f"Colección '{get_collection_name()}' lista para usar en Qdrant.")
            print("=" * 80 + "\n")
        else:
            print("\n⚠️  El proceso no retornó un índice. Verifica los logs arriba.\n")
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario.\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}\n")
        sys.exit(1)
