"""
Tool para actualizar el campo "Areas Comunes" en un lead de Kommo.
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from langchain.tools import tool


def update_data_Areas_Comunes(lead_id: int, areas: str) -> bool:
    """
    Actualiza el campo "Areas Comunes" del lead.

    Args:
        lead_id: ID del lead.
        areas: Áreas comunes que el cliente desea en el inmueble.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    field_id = int(os.getenv("KOMMO_AREAS_COMUNES_FIELD_ID"))

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "custom_fields_values": [
            {
                "field_id": field_id,
                "values": [{"value": areas}]
            }
        ]
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"🏊 Lead {lead_id}: Areas Comunes actualizado a '{areas}'")
        return True
    else:
        print(f"❌ Error actualizando Areas Comunes: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_update_Areas_Comunes_tool(lead_id: int):
    """
    Factory que devuelve una tool de LangChain con el lead_id cerrado en clausura.
    El argumento `areas` lo decide el LLM en base a las áreas que mencionó el cliente.
    """
    @tool
    def update_Areas_Comunes(areas: str) -> str:
        """Actualiza el custom field 'Areas Comunes' del lead actual en Kommo.
        Úsala cuando el cliente mencione áreas comunes que desea o necesita en el
        inmueble/condominio. Argumento: 'areas' = áreas mencionadas, separadas por
        coma (ej: 'piscina, gimnasio', 'parrilla, área de juegos')."""
        ok = update_data_Areas_Comunes(lead_id, areas)
        return (
            f"Areas Comunes del lead {lead_id} actualizado a '{areas}'."
            if ok
            else f"Error al actualizar Areas Comunes del lead {lead_id}."
        )

    return update_Areas_Comunes
