"""
Tool para mover un lead a la etapa "Lead Interesado" en Kommo.
Se activa cuando el cliente hace preguntas exploratorias sobre productos
(sin mostrar intención clara de compra todavía).
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from langchain.tools import tool


def move_lead_to_Lead_Interesado(lead_id: int) -> bool:
    """
    Mueve un lead a la etapa "Lead Interesado".

    Args:
        lead_id: ID del lead a mover.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    pipeline_id = int(os.getenv("KOMMO_PIPELINE_ID"))
    status_id = int(os.getenv("KOMMO_LEAD_INTERESADO_STATUS_ID"))

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "pipeline_id": pipeline_id,
        "status_id": status_id,
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"🔀 Lead {lead_id} movido a 'Lead Interesado' (status {status_id})")
        return True
    else:
        print(f"❌ Error moviendo lead a Lead Interesado: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_move_to_Lead_Interesado_tool(lead_id: int):
    """
    Factory que devuelve una tool de LangChain con el lead_id cerrado en clausura.
    Permite que el agente invoque la acción sin tener que conocer el lead_id.
    """
    @tool
    def move_to_Lead_Interesado() -> str:
        """Mueve el lead actual a la etapa 'Lead Interesado' del pipeline de Kommo.
        Úsala cuando el cliente solo EXPLORA o consulta (información general de la
        inmobiliaria, búsqueda de inmuebles, dudas sobre costos/boleto/políticas o
        mantenimiento) sin mostrar intención clara de alquilar todavía. No requiere
        argumentos."""
        ok = move_lead_to_Lead_Interesado(lead_id)
        return (
            f"Lead {lead_id} movido a 'Lead Interesado'."
            if ok
            else f"Error al mover el lead {lead_id} a 'Lead Interesado'."
        )

    return move_to_Lead_Interesado
