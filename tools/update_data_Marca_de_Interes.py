"""
Tool para actualizar el campo "Marca de Interés" en un lead de Kommo.
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from langchain.tools import tool


def update_data_Marca_de_Interes(lead_id: int, marca: str) -> bool:
    """
    Actualiza el campo "Marca de Interés" del lead.

    Args:
        lead_id: ID del lead.
        marca: Nombre de la marca/producto de interés.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    field_id = int(os.getenv("KOMMO_MARCA_INTERES_FIELD_ID"))

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "custom_fields_values": [
            {
                "field_id": field_id,
                "values": [{"value": marca}]
            }
        ]
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"📌 Lead {lead_id}: Marca de Interés actualizada a '{marca}'")
        return True
    else:
        print(f"❌ Error actualizando Marca de Interés: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_update_Marca_de_Interes_tool(lead_id: int):
    """
    Factory que devuelve una tool de LangChain con el lead_id cerrado en clausura.
    El argumento `marca` lo decide el LLM en base al producto que mencionó el cliente.
    """
    @tool
    def update_Marca_de_Interes(marca: str) -> str:
        """Actualiza el custom field 'Marca de Interés' del lead actual en Kommo.
        Úsala cuando el cliente mencione o pregunte por un inmueble específico del
        inventario. Argumento: 'marca' = identificador del inmueble de interés
        (ID, ej: 'BH-003', o la dirección, ej: 'Rua Bento de Abreu 54')."""
        ok = update_data_Marca_de_Interes(lead_id, marca)
        return (
            f"Marca de Interés del lead {lead_id} actualizada a '{marca}'."
            if ok
            else f"Error al actualizar Marca de Interés del lead {lead_id}."
        )

    return update_Marca_de_Interes
