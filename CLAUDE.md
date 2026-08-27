# Proyecto Kommo — Vendedora Digital "Andrea"

Chatbot de ventas integrado con **Kommo CRM** vía webhooks. Conversa con leads,
consulta un catálogo de productos de salud por **RAG** (LlamaCloud) y opera el
embudo del CRM (mueve etapas + actualiza custom fields) mediante **tool-calling**
con `FunctionAgent` de LlamaIndex.

- **LLM:** OpenAI `gpt-4.1`, `temperature=0` (definido en `model_config/model.yaml`).
- **Memoria:** PostgreSQL/Supabase, una conversación por `lead_id`.
- **RAG:** LlamaCloud, embeddings `text-embedding-3-small` (1536 dim), chunks 512/50.
- **API:** FastAPI + uvicorn, puerto 8000, expuesto con ngrok hacia Kommo.

## Flujo de un mensaje

```
Cliente (WhatsApp/canal) ─► Kommo ─► POST /webhook/kommo (app.py)
   │
   ├─ parse_kommo_webhook  (form-urlencoded → dict, incl. attachment)
   ├─ filtros: outgoing / created_by!=0 / sin texto ni audio / duplicado(5min) / switch IA off
   └─ BackgroundTask process_message(data, lead_id)
          │
          ├─ obtener_texto_de_entrada(data)  → texto tal cual, o si es nota de voz:
          │     descarga del CDN de Kommo → Whisper (whisper-1) → transcripción
          ├─ get_memory_for_user(lead_id)   → ChatMemoryBuffer (Postgres)
          ├─ build_agent_for_lead(lead_id)  → FunctionAgent + 6 tools (closure sobre lead_id)
          ├─ agent.run(message, memory=…)   → LLM decide qué tools invocar
          ├─ update_lead_with_response       → PATCH custom field respuesta + switch=True
          └─ launch_salesbot                 → POST /api/v2/salesbot/run (envía al cliente)
```

## Mapa de módulos

| Ruta | Rol |
|---|---|
| `app.py` | Entrypoint FastAPI. Valida `.env`, dedupe en memoria, webhook handler. |
| `agent.py` | `init_resources(bot_name)` (singletons LLM/índice/prompt/chat_store) + `build_agent_for_lead(lead_id)` (FunctionAgent por mensaje). |
| `Kommo Functions/kommo.py` | Cliente HTTP de Kommo: parseo webhook, switch IA, update lead, launch salesbot. |
| `RAG/rag.py` | Pipeline de ingesta (`python RAG/rag.py` para reindexar). |
| `tools/retrieval.py` | Carga `LlamaCloudIndex` y lo envuelve como `QueryEngineTool` (`similarity_top_k=5`). |
| `tools/move_lead_to_*.py` | 3 tools de etapa (Lead Interesado / Lead Calificado / Cerrar Venta). |
| `tools/update_data_*.py` | 2 tools de custom fields (Marca de Interés, Método de Pago). |
| `tools/Tarea-send_notification_by_*.py` | Notificaciones (email / WhatsApp API). |
| `procesamiento_de_audio/` | Nota de voz → texto. `procesador.py` (entrypoint), `descarga_audio.py` (CDN → temporal), `transcriptor.py` (Whisper). |
| `chat_history/postgres_store.py` | `PostgresChatStore` compartido + `ChatMemoryBuffer` por lead. |
| `prompt/system_prompt.yaml` | System prompt v2.0 (identidad + 8 intenciones + flujos + reglas de tools). |
| `model_config/model.yaml` | Modelo, temperatura, `token_limit` y `table_name` de memoria. |
| `Base_de_Conocimiento/` | 4 PDFs: VitaCalm, CogniBoost, JointFlex, Infusión de Energía Natural. |
| `support_tools/get_pipelines.py` | Lista pipelines y status IDs de Kommo (para poblar `.env`). |
| `support_tools/get_custom_fields.py` | Lista custom fields y enums de Kommo (para poblar `.env`). |

## Convenciones del proyecto

- **Tools de Kommo siguen un patrón uniforme**: función pública `do_something(lead_id, ...)` + factory `get_<tool>_tool(lead_id)` que devuelve un `FunctionTool` con el `lead_id` capturado en closure. El LLM no ve el `lead_id`.
- **Recursos pesados (LLM, índice, retrieval tool, system_prompt, chat_store) se inicializan UNA vez** al arrancar (`init_resources`); el `FunctionAgent` se reconstruye por mensaje porque es barato y permite cerrar las tools sobre el `lead_id` correcto.
- **El nombre del bot** se inyecta vía env `BOT_NAME` (default `Andrea`) y se sustituye en `system_prompt.yaml` con un `.replace("{bot_name}", …)`.
- **Las 3 tools de etapa son mutuamente excluyentes** por turno (regla del prompt). Las 2 de update sí pueden acompañar a una de etapa.
- **El cliente no debe enterarse de las tools ni de la memoria/RAG** — son invisibles.
- **Entrada mixta, salida siempre texto**: el cliente puede escribir o mandar una nota de
  voz; `obtener_texto_de_entrada(data)` normaliza ambos casos a una sola query. El agente
  nunca ve audio y no sintetiza voz — responde en texto vía el Salesbot.
- **La transcripción usa siempre la API de OpenAI** (`whisper-1`), incluso con
  `LLM_PROVIDER=lmstudio`: es un servicio aparte, así que `OPENAI_API_KEY` es obligatoria.

## Variables de entorno requeridas (`.env`)

Validadas en `app.py:_validate_env()` (fail-fast):

- APIs: `OPENAI_API_KEY`, `LLAMA_CLOUD_API_KEY`
- Kommo: `KOMMO_SUBDOMAIN`, `KOMMO_ACCESS_TOKEN`, `KOMMO_PIPELINE_ID`,
  `KOMMO_LEAD_INTERESADO_STATUS_ID`, `KOMMO_LEAD_CALIFICADO_STATUS_ID`,
  `KOMMO_LEAD_CERRAR_VENTA_STATUS_ID`, `KOMMO_MARCA_INTERES_FIELD_ID`,
  `KOMMO_METODO_PAGO_FIELD_ID`
- DB: `DB_USER`, `DB_PASSWORD`, `DB_HOST` (opcional: `DB_PORT=5432`, `DB_NAME=postgres`)
- Adicionales usadas por `kommo.py` (no validadas en startup, pero requeridas):
  `KOMMO_SWITCH_FIELD_ID`, `KOMMO_RESPONSE_FIELD_ID`, `KOMMO_SALESBOT_ID`
- Opcional: `BOT_NAME` (default `Andrea`).

## Comandos

```bash
# Entorno
conda create --name LlamaIndex-proy-Kommo python=3.11
conda activate LlamaIndex-proy-Kommo
pip install -r requirements.txt

# Levantar API
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Exponer a Kommo
ngrok http 8000

# Reindexar el catálogo en LlamaCloud
python RAG/rag.py

# Probar la transcripción de un audio (archivo local o URL)
python procesamiento_de_audio/transcriptor.py ruta/al/audio.ogg

# Consultar metadatos de Kommo para poblar .env
python support_tools/get_pipelines.py
python support_tools/get_custom_fields.py
```

## Bugs / gotchas conocidos

1. **Mismatch de nombre de índice LlamaCloud**:
   `RAG/rag.py` ingesta a `productos_de_salud_aidev15_kommo_crm`, pero
   `tools/retrieval.py:get_index()` tiene como default `productos_de_salud_aidev14_kommo_crm`.
   Si nadie pasa el nombre explícito, el agente consulta un índice distinto del que se reindexa.
2. **Dedupe `processed_messages` en memoria** (dict en `app.py`): se pierde al reiniciar
   uvicorn y no funciona con más de un worker. Para producción mover a Redis/Postgres.
3. **`kommo.py` y los tools no fail-fast en `int(os.getenv(...))`**: si falta una env como
   `KOMMO_SWITCH_FIELD_ID`, revienta con `TypeError: int() argument must be ... not 'NoneType'`
   en pleno request en lugar de al arrancar.
4. **Cuenta bancaria placeholder** en `system_prompt.yaml`: `0000-0000-0000-0000-0000`.
   Reemplazar antes de producción.
5. **`requests` síncrono en endpoint async**: bloquea el event loop. Bajo tráfico real
   conviene migrar a `httpx.AsyncClient`.
6. **`tools/__init__.py`** importa o expone tools — revisar si hay imports que se rompan
   al renombrar/mover archivos.

## Productos del catálogo

VitaCalm · CogniBoost · JointFlex · Infusión de Energía Natural
(un PDF por producto en `Base_de_Conocimiento/`).

## Estado del switch IA por lead

Cada lead tiene un custom field "Switch IA" (`KOMMO_SWITCH_FIELD_ID`).
- Si está `False`: el webhook se ignora (el humano tomó la conversación).
- Si está `True` o el campo no existe: el bot responde.
- Tras responder, el bot lo deja en `True` para mantener la sesión activa.