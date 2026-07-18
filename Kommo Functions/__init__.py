"""
Módulo de funciones para integración con Kommo CRM.
"""

from .kommo import (
    parse_kommo_webhook,
    get_switch_status,
    update_lead_with_response,
    launch_salesbot,
)

__all__ = [
    "parse_kommo_webhook",
    "get_switch_status",
    "update_lead_with_response",
    "launch_salesbot",
]
