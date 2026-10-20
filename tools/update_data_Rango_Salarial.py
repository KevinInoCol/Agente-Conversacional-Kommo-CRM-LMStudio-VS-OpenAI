"""
Tool para actualizar el campo "Rango Salarial" en un lead de Kommo.
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from langchain.tools import tool


def update_data_Rango_Salarial(lead_id: int, rango: str) -> bool:
    """
    Actualiza el campo "Rango Salarial" del lead.

    Args:
        lead_id: ID del lead.
        rango: Ingreso o rango salarial declarado por el cliente.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    field_id = int(os.getenv("KOMMO_RANGO_SALARIAL_FIELD_ID"))

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "custom_fields_values": [
            {
                "field_id": field_id,
                "values": [{"value": rango}]
            }
        ]
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"💰 Lead {lead_id}: Rango Salarial actualizado a '{rango}'")
        return True
    else:
        print(f"❌ Error actualizando Rango Salarial: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_update_Rango_Salarial_tool(lead_id: int):
    """
    Factory que devuelve una tool de LangChain con el lead_id cerrado en clausura.
    El argumento `rango` lo decide el LLM en base al ingreso que mencionó el cliente.
    """
    @tool
    def update_Rango_Salarial(rango: str) -> str:
        """Actualiza el custom field 'Rango Salarial' del lead actual en Kommo.
        Úsala solo cuando el cliente declare explícitamente su ingreso o rango
        salarial mensual. Argumento: 'rango' = ingreso declarado por el cliente,
        tal como lo dijo (ej: 'R$ 5.000', 'entre R$ 4.000 y R$ 6.000')."""
        ok = update_data_Rango_Salarial(lead_id, rango)
        return (
            f"Rango Salarial del lead {lead_id} actualizado a '{rango}'."
            if ok
            else f"Error al actualizar Rango Salarial del lead {lead_id}."
        )

    return update_Rango_Salarial
