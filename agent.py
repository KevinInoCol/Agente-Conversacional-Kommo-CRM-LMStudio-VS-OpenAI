"""
Módulo Agente IA (LangChain / LangGraph) para el flujo de Kommo CRM.

Migrado de LlamaIndex `FunctionAgent` a LangChain `create_agent` (la API actual
recomendada; ver docs.langchain.com/oss/python/langchain/agents).

Configuración modular:
- LLM + parámetros de memoria: model_config/model.yaml
- System prompt:                prompt/system_prompt.yaml
- Memoria (checkpointer):       chat_history/  (PostgreSQL / Supabase)
- Credenciales DB y BOT_NAME:   .env

Arquitectura tool-calling:
- `init_resources(bot_name)` se llama UNA vez al arrancar el app. Carga el LLM
  (ChatOpenAI), el índice (LlamaCloud), arma la retrieval tool, renderiza el
  system_prompt y crea el checkpointer (Postgres). No devuelve nada: deja los
  recursos como singletons de módulo.

- `build_agent_for_lead(lead_id)` se llama por cada mensaje entrante. Construye
  un agente ligero (`create_agent`) con los 10 tools enlazados a ese lead_id:
    1. busqueda_en_base_conocimiento (RAG de políticas/FAQ, compartido)
    2. gsheets_buscar_inmuebles (inventario en Google Sheets, compartido)
    3. move_to_Lead_Interesado
    4. move_to_Lead_Calificado
    5. move_to_Cerrar_Venta
    6. update_Tipo_de_Inmueble
    7. update_Metodo_de_Pago
    8. update_Rango_Salarial
    9. update_Metraje
    10. update_Areas_Comunes
  El agente DECIDE cuándo invocar cada tool según el contexto. La memoria por
  lead se logra pasando `thread_id=lead_id` al invocar el agente (lo hace app.py).
"""

import os
import re
from pathlib import Path

import yaml
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from chat_history import build_checkpointer
from tools.retrieval import get_index, get_retrieval_tool
from tools.buscar_inmuebles import get_buscar_inmuebles_tool
from tools.move_lead_to_Lead_Interesado import get_move_to_Lead_Interesado_tool
from tools.move_lead_to_Lead_Calificado import get_move_to_Lead_Calificado_tool
from tools.move_lead_to_Cerrar_Venta import get_move_to_Cerrar_Venta_tool
from tools.update_data_Tipo_de_Inmueble import get_update_Tipo_de_Inmueble_tool
from tools.update_data_Metodo_de_Pago import get_update_Metodo_de_Pago_tool
from tools.update_data_Rango_Salarial import get_update_Rango_Salarial_tool
from tools.update_data_Metraje import get_update_Metraje_tool
from tools.update_data_Areas_Comunes import get_update_Areas_Comunes_tool

# ──────────────────────────────────────────────
# 0. CARGA DE CONFIGURACIÓN MODULAR
# ──────────────────────────────────────────────

ROOT = Path(__file__).parent
LLM_CONFIG_PATH = ROOT / "model_config" / "model.yaml"
PROMPT_CONFIG_PATH = ROOT / "prompt" / "system_prompt.yaml"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _render_system_prompt(bot_name: str) -> str:
    """Carga el system_prompt.yaml y reemplaza los placeholders {variable}."""
    prompt_cfg = _load_yaml(PROMPT_CONFIG_PATH)
    return prompt_cfg["system_prompt"].replace("{bot_name}", bot_name)


# ──────────────────────────────────────────────
# 1. RECURSOS COMPARTIDOS (singletons, init una vez)
# ──────────────────────────────────────────────

_llm = None
_retrieval_tool = None
_inmuebles_tool = None
_system_prompt = None
_checkpointer = None
_strip_thinking = False


def _build_llm(llm_cfg: dict):
    """
    Construye el ChatModel según el proveedor activo. Devuelve (llm, strip_thinking).

    El proveedor se decide con la variable de entorno LLM_PROVIDER (gana sobre el
    yaml). Como LM Studio expone una API compatible con OpenAI, ambos proveedores
    usan `ChatOpenAI`; para LM Studio solo cambian `base_url` y `api_key`.
    """
    provider = os.getenv("LLM_PROVIDER", llm_cfg.get("provider", "openai")).strip().lower()
    temperature = llm_cfg.get("temperature", 0)

    if provider == "lmstudio":
        lm_cfg = llm_cfg.get("lmstudio", {})
        model = os.getenv("LMSTUDIO_MODEL") or lm_cfg.get("model")
        base_url = os.getenv("LMSTUDIO_BASE_URL") or lm_cfg.get(
            "base_url", "http://localhost:1234/v1"
        )
        # LM Studio no valida la key, pero LangChain exige que exista.
        api_key = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
        print(f"🧠 LLM activo: LM Studio → modelo '{model}' @ {base_url}")
        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            base_url=base_url,
            api_key=api_key,
        )
        return llm, bool(lm_cfg.get("strip_thinking", True))

    # Por defecto: OpenAI (nube). API key desde OPENAI_API_KEY en el .env.
    # Pattern from: docs.langchain.com/oss/python/langchain/models
    oa_cfg = llm_cfg.get("openai", {})
    model = os.getenv("OPENAI_MODEL") or oa_cfg.get("model", "gpt-4.1")
    print(f"🧠 LLM activo: OpenAI → modelo '{model}'")
    return ChatOpenAI(model=model, temperature=temperature), False


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def clean_agent_response(text: str) -> str:
    """
    Limpia la respuesta final del agente antes de enviarla al cliente.

    Los modelos "reasoning" (ej. Qwen3 en LM Studio) emiten su cadena de
    pensamiento en bloques <think>...</think>. Si no se quita, terminaría
    guardada en Kommo y enviada al cliente. Solo actúa cuando el proveedor
    activo lo requiere (`_strip_thinking`); para OpenAI es un no-op.
    """
    if not text:
        return text
    if not _strip_thinking:
        return text.strip()

    cleaned = _THINK_BLOCK.sub("", text)
    # Si quedó un </think> suelto (razonamiento sin etiqueta de apertura, como a
    # veces devuelve LM Studio), nos quedamos con lo que viene tras el último cierre.
    lowered = cleaned.lower()
    if "</think>" in lowered:
        cleaned = cleaned[lowered.rfind("</think>") + len("</think>"):]
    return cleaned.strip()


def init_resources(bot_name: str) -> None:
    """
    Inicializa los recursos compartidos del agente (LLM, índice, retrieval tool,
    system prompt y checkpointer de memoria). Llamar una sola vez al arrancar.
    """
    global _llm, _retrieval_tool, _inmuebles_tool, _system_prompt, _checkpointer
    global _strip_thinking

    config = _load_yaml(LLM_CONFIG_PATH)
    llm_cfg = config["llm"]

    _llm, _strip_thinking = _build_llm(llm_cfg)

    index = get_index()
    _retrieval_tool = get_retrieval_tool(index)

    # Tool de inventario (Google Sheets). Compartida entre todos los leads.
    _inmuebles_tool = get_buscar_inmuebles_tool()

    _system_prompt = _render_system_prompt(bot_name)

    _checkpointer = build_checkpointer()


# ──────────────────────────────────────────────
# 2. AGENTE POR LEAD (lightweight, recreado por mensaje)
# ──────────────────────────────────────────────

def build_agent_for_lead(lead_id: int):
    """
    Construye un agente (`create_agent`) con tools enlazadas al lead_id especificado.
    Se recrea por cada mensaje entrante: el LLM, el índice, la retrieval tool y el
    checkpointer son singletons cacheados; solo el agente y las tools de acción se
    reconstruyen (es barato) para cerrar las tools sobre el lead_id correcto.

    Devuelve un grafo compilado de LangGraph. Se invoca con:
        agent.invoke(
            {"messages": [{"role": "user", "content": texto}]},
            {"configurable": {"thread_id": str(lead_id)}},
        )
    """
    if _llm is None:
        raise RuntimeError(
            "Recursos no inicializados. Llama a init_resources(bot_name) primero."
        )

    tools = [
        _retrieval_tool,
        _inmuebles_tool,
        get_move_to_Lead_Interesado_tool(lead_id),
        get_move_to_Lead_Calificado_tool(lead_id),
        get_move_to_Cerrar_Venta_tool(lead_id),
        get_update_Tipo_de_Inmueble_tool(lead_id),
        get_update_Metodo_de_Pago_tool(lead_id),
        get_update_Rango_Salarial_tool(lead_id),
        get_update_Metraje_tool(lead_id),
        get_update_Areas_Comunes_tool(lead_id),
    ]

    # Pattern from: docs.langchain.com/oss/python/langchain/agents
    return create_agent(
        model=_llm,
        tools=tools,
        system_prompt=_system_prompt,
        checkpointer=_checkpointer,
    )
