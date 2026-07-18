"""
Gestión del histórico de conversación (memoria de corto plazo) en
PostgreSQL / Supabase, ahora vía el checkpointer de LangGraph.

Con LangChain/LangGraph la memoria conversacional NO se maneja con un
ChatMemoryBuffer: se persiste el estado del agente (los `messages`) mediante un
`checkpointer`. Cada conversación se aísla con un `thread_id` (aquí, el lead_id
de Kommo) que se pasa en cada invocación del agente.

- Se crea UN checkpointer al arrancar la API y se comparte entre todos los leads.
- `PostgresSaver.setup()` crea automáticamente sus tablas la primera vez.

Las credenciales de DB vienen del .env (DB_USER, DB_PASSWORD, DB_HOST,
DB_PORT, DB_NAME, DB_SSLMODE).
"""

import os
from urllib.parse import quote_plus

from langgraph.checkpoint.postgres import PostgresSaver


def _build_database_url() -> str:
    """
    Construye la URL de conexión sync (psycopg) que usa PostgresSaver.

    Ojo: a diferencia de la versión LlamaIndex, NO se usa el driver asyncpg
    (`postgresql+asyncpg://`) sino el formato estándar `postgresql://`, porque
    PostgresSaver trabaja con psycopg de forma síncrona.
    """
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "postgres")
    # Supabase normalmente requiere SSL. Por defecto 'require'; ponlo en
    # 'disable' en el .env para Postgres local sin SSL.
    DB_SSLMODE = os.getenv("DB_SSLMODE", "require")

    if not all([DB_USER, DB_PASSWORD, DB_HOST]):
        raise ValueError(
            "❌ Faltan variables de base de datos en .env\n"
            "Requeridas: DB_USER, DB_PASSWORD, DB_HOST"
        )

    return (
        f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?sslmode={DB_SSLMODE}"
    )


# Se mantiene una referencia al context manager para que la conexión siga
# abierta durante toda la vida de la app (no se debe cerrar al salir de la
# función). Patrón típico para apps de larga duración (FastAPI).
_checkpointer_cm = None


def build_checkpointer() -> PostgresSaver:
    """
    Crea el PostgresSaver (checkpointer) compartido y crea sus tablas si no existen.
    Se llama UNA vez al arrancar la API.
    """
    global _checkpointer_cm

    _checkpointer_cm = PostgresSaver.from_conn_string(_build_database_url())
    checkpointer = _checkpointer_cm.__enter__()
    checkpointer.setup()  # crea las tablas de checkpoints si no existen
    return checkpointer
