"""
Tool para actualizar el campo "Método de Pago" en un lead de Kommo.
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from langchain.tools import tool


def update_data_Metodo_de_Pago(lead_id: int, metodo: str) -> bool:
    """
    Actualiza el campo "Método de Pago" del lead.

    Args:
        lead_id: ID del lead.
        metodo: Método de pago indicado por el cliente.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    field_id = int(os.getenv("KOMMO_METODO_PAGO_FIELD_ID"))

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "custom_fields_values": [
            {
                "field_id": field_id,
                "values": [{"value": metodo}]
            }
        ]
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"💳 Lead {lead_id}: Método de Pago actualizado a '{metodo}'")
        return True
    else:
        print(f"❌ Error actualizando Método de Pago: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_update_Metodo_de_Pago_tool(lead_id: int):
    """
    Factory que devuelve una tool de LangChain con el lead_id cerrado en clausura.
    El argumento `metodo` lo decide el LLM en base al método que mencionó el cliente.
    """
    @tool
    def update_Metodo_de_Pago(metodo: str) -> str:
        """Actualiza el custom field 'Método de Pago' del lead actual en Kommo.
        Úsala cuando el cliente indique cómo quiere pagar o pregunte por un método
        de pago concreto. Argumento: 'metodo' = método declarado por el cliente
        (ej: 'tarjeta de crédito', 'transferencia', 'efectivo')."""
        ok = update_data_Metodo_de_Pago(lead_id, metodo)
        return (
            f"Método de Pago del lead {lead_id} actualizado a '{metodo}'."
            if ok
            else f"Error al actualizar Método de Pago del lead {lead_id}."
        )

    return update_Metodo_de_Pago
