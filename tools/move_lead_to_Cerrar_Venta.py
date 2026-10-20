"""
Tool para mover un lead a la etapa "Cerrar Venta" en Kommo.
Se activa cuando el cliente confirma que avanza: agenda una visita en firme,
se compromete a enviar la documentación o pide reservar el inmueble.
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from langchain.tools import tool


def move_lead_to_Cerrar_Venta(lead_id: int) -> bool:
    """
    Mueve un lead a la etapa "Cerrar Venta" (el cliente confirmó que avanza).

    Args:
        lead_id: ID del lead a mover.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    pipeline_id = int(os.getenv("KOMMO_PIPELINE_ID"))
    status_id = int(os.getenv("KOMMO_LEAD_CERRAR_VENTA_STATUS_ID"))

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
        print(f"🔀 Lead {lead_id} movido a 'Cerrar Venta' (status {status_id})")
        return True
    else:
        print(f"❌ Error moviendo lead a Cerrar Venta: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_move_to_Cerrar_Venta_tool(lead_id: int):
    """
    Factory que devuelve una tool de LangChain con el lead_id cerrado en clausura.
    """
    @tool
    def move_to_Cerrar_Venta() -> str:
        """Mueve el lead actual a la etapa 'Cerrar Venta' del pipeline de Kommo.
        Úsala SOLO cuando el cliente CONFIRMA que avanza de forma inminente: agenda una
        visita en firme ('confirmo la visita el sábado'), se compromete a enviar la
        documentación/ficha cadastral ('ahora te envío mis documentos'), o pide reservar
        el inmueble. No la uses si solo pregunta por requisitos o quiere alquilar sin
        confirmar el paso — para eso usa move_to_Lead_Calificado. No requiere argumentos."""
        ok = move_lead_to_Cerrar_Venta(lead_id)
        return (
            f"Lead {lead_id} movido a 'Cerrar Venta'."
            if ok
            else f"Error al mover el lead {lead_id} a 'Cerrar Venta'."
        )

    return move_to_Cerrar_Venta
