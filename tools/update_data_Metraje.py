"""
Tool para actualizar el campo "Metraje" en un lead de Kommo.
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from langchain.tools import tool


def update_data_Metraje(lead_id: int, metraje: str) -> bool:
    """
    Actualiza el campo "Metraje" del lead.

    Args:
        lead_id: ID del lead.
        metraje: Metros cuadrados que busca el cliente.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    field_id = int(os.getenv("KOMMO_METRAJE_FIELD_ID"))

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "custom_fields_values": [
            {
                "field_id": field_id,
                "values": [{"value": metraje}]
            }
        ]
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"📐 Lead {lead_id}: Metraje actualizado a '{metraje}'")
        return True
    else:
        print(f"❌ Error actualizando Metraje: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_update_Metraje_tool(lead_id: int):
    """
    Factory que devuelve una tool de LangChain con el lead_id cerrado en clausura.
    El argumento `metraje` lo decide el LLM en base al tamaño que mencionó el cliente.
    """
    @tool
    def update_Metraje(metraje: str) -> str:
        """Actualiza el custom field 'Metraje' del lead actual en Kommo.
        Úsala cuando el cliente indique el tamaño (metros cuadrados) que busca.
        Argumento: 'metraje' = metraje declarado por el cliente
        (ej: '60 m²', 'mínimo 80 m²', 'entre 50 y 70 m²')."""
        ok = update_data_Metraje(lead_id, metraje)
        return (
            f"Metraje del lead {lead_id} actualizado a '{metraje}'."
            if ok
            else f"Error al actualizar Metraje del lead {lead_id}."
        )

    return update_Metraje
