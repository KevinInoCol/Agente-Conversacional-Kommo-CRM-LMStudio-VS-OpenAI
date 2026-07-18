"""
Entrypoint FastAPI del chatbot Kommo (arquitectura tool-calling).

Recibe webhooks de Kommo, construye un agente LangChain específico para el lead,
ejecuta el agente con memoria persistente y deja que el LLM decida cuándo
invocar las tools de Kommo (mover etapa, actualizar custom fields). Luego
guarda la respuesta limpia en el lead y dispara el salesbot.
"""

import os
import sys
import time
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks

load_dotenv()

# ──────────────────────────────────────────────
# Validación de variables de entorno (fail-fast)
# ──────────────────────────────────────────────

REQUIRED_ENV_VARS = [
    # APIs externas
    "OPENAI_API_KEY",
    "LLAMA_CLOUD_API_KEY",
    # Kommo
    "KOMMO_SUBDOMAIN",
    "KOMMO_ACCESS_TOKEN",
    "KOMMO_PIPELINE_ID",
    "KOMMO_LEAD_INTERESADO_STATUS_ID",
    "KOMMO_LEAD_CALIFICADO_STATUS_ID",
    "KOMMO_LEAD_CERRAR_VENTA_STATUS_ID",
    "KOMMO_MARCA_INTERES_FIELD_ID",
    "KOMMO_METODO_PAGO_FIELD_ID",
    # Memoria (Supabase/Postgres)
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
]


def _validate_env():
    """Verifica que todas las variables requeridas estén en el .env.
    Falla con un mensaje claro si falta alguna, en vez de errores silenciosos
    al primer uso (ej: int(None) → TypeError dentro de un tool)."""
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        print("\n" + "=" * 60)
        print("❌ Faltan variables de entorno requeridas en .env:")
        for var in missing:
            print(f"   - {var}")
        print("=" * 60 + "\n")
        sys.exit(1)
    print(f"✅ {len(REQUIRED_ENV_VARS)} variables de entorno verificadas.")


_validate_env()

sys.path.append(os.path.join(os.path.dirname(__file__), "Kommo Functions"))
from kommo import parse_kommo_webhook, update_lead_with_response, launch_salesbot, get_switch_status

from agent import init_resources, build_agent_for_lead, clean_agent_response

BOT_NAME = os.getenv("BOT_NAME", "Andrea")

# Deduplicación: evita procesar el mismo mensaje si Kommo reenvía el webhook
processed_messages: dict[str, float] = {}
DEDUP_WINDOW_SECONDS = 300  # 5 minutos

print(f"🤖 Inicializando agente {BOT_NAME}...")
init_resources(bot_name=BOT_NAME)
print("✅ LLM (LangChain), índice (LlamaCloud) y memoria (Postgres/Supabase) listos.")

app = FastAPI(title="Kommo AI Chatbot")


def is_duplicate(lead_id: str, text: str) -> bool:
    """Verifica si este mensaje ya fue procesado recientemente (deduplicación)."""
    now = time.time()

    expired = [k for k, v in processed_messages.items() if now - v > DEDUP_WINDOW_SECONDS]
    for k in expired:
        del processed_messages[k]

    key = f"{lead_id}:{text}"
    if key in processed_messages:
        return True

    processed_messages[key] = now
    return False


async def process_message(message_text: str, lead_id: str):
    """
    Procesa el mensaje en segundo plano:
    1. Agente (create_agent) con tools enlazadas al lead_id.
    2. agent.invoke() con thread_id=lead_id — la memoria persistente la maneja el
       checkpointer de Postgres; el LLM decide qué tools invocar.
    3. Guarda respuesta final en Kommo + lanza salesbot.
    """
    try:
        agent = build_agent_for_lead(int(lead_id))

        # thread_id aísla la conversación de cada lead (memoria por lead).
        config = {"configurable": {"thread_id": str(lead_id)}}
        result = agent.invoke(
            {"messages": [{"role": "user", "content": message_text}]},
            config,
        )
        # clean_agent_response quita los bloques <think>...</think> de modelos
        # reasoning (ej. Qwen3 en LM Studio). Para OpenAI es un simple .strip().
        response_text = clean_agent_response(result["messages"][-1].content)

        print(f"🤖 Respuesta: {response_text[:80]}...")

        update_lead_with_response(lead_id, response_text)
        print(f"✅ Lead {lead_id} actualizado: respuesta guardada + switch activado")

        launch_salesbot(lead_id)

    except Exception as e:
        print(f"❌ Error procesando mensaje: {str(e)}")


@app.get("/")
async def root():
    return {"status": "ok", "message": "Kommo AI Chatbot activo"}


@app.post("/webhook/kommo")
async def kommo_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()

    data = parse_kommo_webhook(body)

    message_text = data.get("text", "")
    lead_id = data.get("lead_id")
    message_type = data.get("type", "")
    created_by = data.get("created_by")

    if message_type and message_type == "outgoing":
        return {"status": "ignored", "reason": "outgoing message"}

    if created_by and str(created_by) != "0":
        return {"status": "ignored", "reason": "system message"}

    if not message_text or not lead_id:
        return {"status": "ignored", "reason": "missing data"}

    if len(message_text.strip()) < 1:
        return {"status": "ignored", "reason": "empty message"}

    if is_duplicate(lead_id, message_text):
        print(f"⏭️ Webhook duplicado ignorado (lead {lead_id})")
        return {"status": "ignored", "reason": "duplicate webhook"}

    if not get_switch_status(lead_id):
        print(f"🔴 Switch IA DESACTIVADO para lead {lead_id}")
        return {"status": "ignored", "reason": "AI switch off"}

    print(f"📩 Webhook recibido de Kommo!")
    print(f"💬 Mensaje: '{message_text[:50]}...' | Lead ID: {lead_id}")

    background_tasks.add_task(process_message, message_text, lead_id)

    return {"status": "ok", "message": "processing"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
