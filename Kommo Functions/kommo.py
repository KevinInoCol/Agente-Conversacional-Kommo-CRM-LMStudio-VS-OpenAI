import os
import requests
from urllib.parse import parse_qs


PREFIJO_MENSAJE = "message[add][0]"


def parse_kommo_webhook(body: bytes) -> dict:
    """
    Parsea el webhook de Kommo (form-urlencoded).

    Además de los campos del mensaje, extrae el bloque `attachment` (link, tipo
    y nombre de archivo) que Kommo manda cuando el cliente envía una nota de voz
    o un archivo. El audio NO viaja en el webhook: viene un link al CDN, que es
    lo que descarga y transcribe `procesamiento_de_audio`.

    Se guarda también `raw` (el dict crudo de parse_qs) para poder depurar
    payloads de canales que nombran los campos de forma distinta.
    """
    parsed = parse_qs(body.decode('utf-8'))

    def get_value(key):
        values = parsed.get(key, [None])
        return values[0] if values else None

    plano = {k: v[0] for k, v in parsed.items() if v}

    return {
        "text": get_value(f"{PREFIJO_MENSAJE}[text]"),
        "chat_id": get_value(f"{PREFIJO_MENSAJE}[chat_id]"),
        "lead_id": get_value(f"{PREFIJO_MENSAJE}[element_id]"),
        "entity_type": get_value(f"{PREFIJO_MENSAJE}[entity_type]"),
        "type": get_value(f"{PREFIJO_MENSAJE}[type]"),  # incoming/outgoing
        "created_by": get_value(f"{PREFIJO_MENSAJE}[created_by]"),  # 0 = cliente
        "author_id": get_value(f"{PREFIJO_MENSAJE}[author][id]"),
        "author_type": get_value(f"{PREFIJO_MENSAJE}[author][type]"),  # contact/user
        "attachment": _parse_attachment(parsed, get_value),
        "raw": plano,
    }


def _parse_attachment(parsed: dict, get_value) -> dict:
    """
    Extrae el adjunto del webhook: {"type", "link", "file_name", "file_size"}.

    Fallback: si Kommo (o el canal) usa una clave distinta a la documentada, se
    barre el payload buscando cualquier clave que contenga "attachment" + "link"
    o "url", para no perder el audio por un cambio de nombre en el campo.
    """
    adjunto = {
        "type": get_value(f"{PREFIJO_MENSAJE}[attachment][type]"),
        "link": get_value(f"{PREFIJO_MENSAJE}[attachment][link]"),
        "file_name": get_value(f"{PREFIJO_MENSAJE}[attachment][file_name]"),
        "file_size": get_value(f"{PREFIJO_MENSAJE}[attachment][file_size]"),
    }

    if not adjunto["link"]:
        for clave, valores in parsed.items():
            clave_baja = clave.lower()
            if "attachment" in clave_baja and ("link" in clave_baja or "url" in clave_baja):
                adjunto["link"] = valores[0] if valores else None
                break

    return {k: v for k, v in adjunto.items() if v}


def get_switch_status(lead_id: int) -> bool:
    """Verifica si el Switch de IA está activo para este lead"""
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    switch_field_id = os.getenv("KOMMO_SWITCH_FIELD_ID")
    
    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error obteniendo lead: {response.status_code}")
        return False
    
    lead_data = response.json()
    custom_fields = lead_data.get("custom_fields_values") or []
    
    for field in custom_fields:
        if field.get("field_id") == int(switch_field_id):
            values = field.get("values", [])
            if values:
                # Checkbox: True/False o "1"/"0"
                value = values[0].get("value")
                is_active = value in [True, "true", "1", 1]
                print(f"🔍 Switch IA para lead {lead_id}: {value} -> {'ACTIVO' if is_active else 'INACTIVO'}")
                return is_active
    
    # Si no existe el campo, asumimos que está activo por defecto
    print(f"🔍 Switch IA para lead {lead_id}: campo no encontrado -> ACTIVO por defecto")
    return True


def update_lead_with_response(lead_id: int, response_text: str):
    """Actualiza el lead con la respuesta de IA y activa el switch"""
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    response_field_id = os.getenv("KOMMO_RESPONSE_FIELD_ID")
    switch_field_id = os.getenv("KOMMO_SWITCH_FIELD_ID")
    
    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "custom_fields_values": [
            {
                "field_id": int(response_field_id),
                "values": [{"value": response_text}]
            },
            {
                "field_id": int(switch_field_id),
                "values": [{"value": True}]
            }
        ]
    }
    
    response = requests.patch(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        return True
    else:
        print(f"❌ Error actualizando lead: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def launch_salesbot(lead_id: int):
    """Lanza el Salesbot para que envíe la respuesta al cliente"""
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    bot_id = os.getenv("KOMMO_SALESBOT_ID")
    
    # Endpoint correcto: API v2
    url = f"https://{subdomain}.kommo.com/api/v2/salesbot/run"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = [
        {
            "bot_id": int(bot_id),
            "entity_id": int(lead_id),
            "entity_type": 2
        }
    ]
    
    response = requests.post(url, headers=headers, json=payload)
    
    # 200 = OK, 202 = Accepted (ambos son éxito)
    if response.status_code in [200, 202]:
        print(f"✅ Salesbot {bot_id} lanzado para lead {lead_id}")
        return True
    else:
        print(f"❌ Error al lanzar Salesbot: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False