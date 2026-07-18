# Agente Conversacional Kommo CRM — LM Studio vs OpenAI

Chatbot de ventas ("Andrea") para una **inmobiliaria** (alquiler de inmuebles),
integrado con **Kommo CRM** vía webhooks. Conversa con los leads, consulta un
catálogo de políticas/FAQ por **RAG**, busca inmuebles en un **Google Sheets**, y
opera el embudo del CRM (mueve etapas + actualiza custom fields) mediante
**tool-calling** con un agente de LangChain/LangGraph.

Su rasgo distintivo: permite **elegir el LLM** entre **OpenAI (nube)** y
**LM Studio (modelo local, p. ej. Qwen3)** cambiando una sola variable de entorno.

## Arquitectura

```
Cliente (WhatsApp/canal) ─► Kommo ─► POST /webhook/kommo (app.py)
   │
   ├─ filtros: outgoing / no-cliente / vacío / duplicado(5min) / switch IA off
   └─ BackgroundTask process_message(text, lead_id)
          ├─ build_agent_for_lead(lead_id)  → create_agent (LangGraph) + 7 tools
          ├─ agent.invoke(msg, thread_id=lead_id)  → memoria por lead (checkpointer Postgres)
          ├─ clean_agent_response()          → quita <think> de modelos reasoning
          ├─ update_lead_with_response       → guarda respuesta + activa switch IA
          └─ launch_salesbot                 → envía el mensaje al cliente
```

- **LLM:** OpenAI `gpt-4.1` **o** LM Studio (`qwen/qwen3-8b`, etc.), seleccionable por `LLM_PROVIDER`.
- **Memoria:** PostgreSQL/Supabase vía el checkpointer de LangGraph (`thread_id = lead_id`).
- **RAG:** Qdrant como vector store + LlamaParse para parsear los PDFs. Embeddings `text-embedding-3-small`.
- **Inventario:** Google Sheets (gspread) como única fuente de verdad de los inmuebles.
- **API:** FastAPI + uvicorn (puerto 8000), expuesto a Kommo con ngrok.

## Selección de LLM (OpenAI ↔ LM Studio)

En el `.env`:

```bash
LLM_PROVIDER=openai      # usa OpenAI gpt-4.1
# LLM_PROVIDER=lmstudio  # usa tu modelo local en LM Studio
```

Para LM Studio: carga el modelo, arranca su servidor local (puerto 1234) con una
ventana de contexto suficiente (≥ 8k, recomendado 16k), y reinicia uvicorn. El
modelo debe soportar **tool-calling** (function calling) para operar el CRM.

## Puesta en marcha

```bash
# 1. Entorno
conda create --name LangChain-LlamaIndex-Kommo python=3.11
conda activate LangChain-LlamaIndex-Kommo
pip install -r requirements.txt

# 2. Configuración
cp .env.example .env        # y rellena tus credenciales
#   Coloca el JSON de la service account de Google en credentials/

# 3. Indexar el catálogo en Qdrant (una vez)
python RAG/rag.py

# 4. Levantar la API
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# 5. Exponer a Kommo
ngrok http 8000             # registra la URL pública en el webhook de Kommo
```

## Embudo (pipeline de Kommo)

El agente mueve el lead según la intención detectada en cada mensaje:

| Etapa | Se activa cuando el cliente… |
|---|---|
| **Lead Interesado** | Explora/consulta (info, búsqueda, costos, políticas) sin intención clara. |
| **Lead Calificado** | Muestra intención clara: quiere un inmueble, pide requisitos o agendar visita. |
| **Cerrar Venta** | Confirma: agenda visita en firme, envía documentación o reserva. |

## Estructura

| Ruta | Rol |
|---|---|
| `app.py` | Entrypoint FastAPI: validación de env, webhook, deduplicación. |
| `agent.py` | Construye el LLM (OpenAI/LM Studio), el agente por lead y limpia el `<think>`. |
| `Kommo Functions/kommo.py` | Cliente HTTP de Kommo (webhook, switch IA, update lead, salesbot). |
| `RAG/rag.py` | Pipeline de ingesta a Qdrant (LlamaParse + embeddings). |
| `vector_store.py` | Config compartida de Qdrant (fuente única para ingesta y consulta). |
| `tools/` | RAG (`knowledge_base`), inventario (`buscar_inmuebles`) y tools de Kommo. |
| `chat_history/postgres_store.py` | Checkpointer de LangGraph (memoria por lead). |
| `prompt/system_prompt.yaml` | System prompt (identidad + intenciones + flujos + reglas de tools). |
| `model_config/model.yaml` | Config del LLM por proveedor. |

## Seguridad

- El `.env` y `credentials/` están en `.gitignore`: **nunca** se suben al repo.
- Usa `.env.example` como plantilla.
