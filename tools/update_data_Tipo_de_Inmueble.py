"""
Tool para actualizar el campo "Tipo de Inmueble" en un lead de Kommo.
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from langchain.tools import tool


def update_data_Tipo_de_Inmueble(lead_id: int, tipo: str) -> bool:
    """
    Actualiza el campo "Tipo de Inmueble" del lead.

    Args:
        lead_id: ID del lead.
        tipo: Tipo de inmueble que busca el cliente.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    field_id = int(os.getenv("KOMMO_TIPO_INMUEBLE_FIELD_ID"))

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "custom_fields_values": [
            {
                "field_id": field_id,
                "values": [{"value": tipo}]
            }
        ]
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"🏠 Lead {lead_id}: Tipo de Inmueble actualizado a '{tipo}'")
        return True
    else:
        print(f"❌ Error actualizando Tipo de Inmueble: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_update_Tipo_de_Inmueble_tool(lead_id: int):
    """
    Factory que devuelve una tool de LangChain con el lead_id cerrado en clausura.
    El argumento `tipo` lo decide el LLM en base al tipo que mencionó el cliente.
    """
    @tool
    def update_Tipo_de_Inmueble(tipo: str) -> str:
        """Actualiza el custom field 'Tipo de Inmueble' del lead actual en Kommo.
        Úsala cuando el cliente indique qué tipo de inmueble busca.
        Argumento: 'tipo' = tipo declarado por el cliente
        (ej: 'Casa', 'Departamento', 'Kitnet')."""
        ok = update_data_Tipo_de_Inmueble(lead_id, tipo)
        return (
            f"Tipo de Inmueble del lead {lead_id} actualizado a '{tipo}'."
            if ok
            else f"Error al actualizar Tipo de Inmueble del lead {lead_id}."
        )

    return update_Tipo_de_Inmueble
