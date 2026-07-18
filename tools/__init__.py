"""
Tools del agente: retrieval (consulta al índice) + acciones sobre Kommo CRM.

Cada acción expone dos cosas:
- La función imperativa original (move_lead_to_X, update_data_X) — útil para tests
- Una factory get_<nombre>_tool(lead_id) que devuelve una tool de LangChain con el
  lead_id cerrado en clausura, lista para registrarse en el agente (create_agent).
"""

from .retrieval import get_index, get_retrieval_tool
from .buscar_inmuebles import get_buscar_inmuebles_tool
from .move_lead_to_Lead_Interesado import (
    move_lead_to_Lead_Interesado,
    get_move_to_Lead_Interesado_tool,
)
from .move_lead_to_Lead_Calificado import (
    move_lead_to_Lead_Calificado,
    get_move_to_Lead_Calificado_tool,
)
from .move_lead_to_Cerrar_Venta import (
    move_lead_to_Cerrar_Venta,
    get_move_to_Cerrar_Venta_tool,
)
from .update_data_Marca_de_Interes import (
    update_data_Marca_de_Interes,
    get_update_Marca_de_Interes_tool,
)
from .update_data_Metodo_de_Pago import (
    update_data_Metodo_de_Pago,
    get_update_Metodo_de_Pago_tool,
)

__all__ = [
    "get_index",
    "get_retrieval_tool",
    "get_buscar_inmuebles_tool",
    "move_lead_to_Lead_Interesado",
    "move_lead_to_Lead_Calificado",
    "move_lead_to_Cerrar_Venta",
    "update_data_Marca_de_Interes",
    "update_data_Metodo_de_Pago",
    "get_move_to_Lead_Interesado_tool",
    "get_move_to_Lead_Calificado_tool",
    "get_move_to_Cerrar_Venta_tool",
    "get_update_Marca_de_Interes_tool",
    "get_update_Metodo_de_Pago_tool",
]
