"""
Puente entre el webhook de Kommo y el agente: resuelve el TEXTO de entrada.

El cliente puede escribir o mandar una nota de voz. El agente solo entiende
texto, así que este módulo normaliza ambos casos a una sola query:

    texto  ─────────────────────────────────────► se usa tal cual
    audio  ─► descarga ─► Whisper ─► transcripción ─► se usa como query

La salida del agente siempre es texto (la manda el Salesbot de Kommo), así que
aquí no hay síntesis de voz: el flujo de audio es solo de entrada.

`obtener_texto_de_entrada` es la ÚNICA función que necesita app.py.
"""

from pathlib import Path
from urllib.parse import urlparse

try:  # import normal cuando se usa como paquete (app.py, agente)
    from procesamiento_de_audio.descarga_audio import EXTENSIONES_SOPORTADAS
    from procesamiento_de_audio.transcriptor import transcribir_audio_desde_url
except ImportError:  # ejecución directa: python procesamiento_de_audio/procesador.py
    from descarga_audio import EXTENSIONES_SOPORTADAS
    from transcriptor import transcribir_audio_desde_url

# Valores de `attachment[type]` que Kommo usa para notas de voz y audios.
# ("voice" = nota de voz de WhatsApp; "audio" = archivo de audio adjunto.)
TIPOS_DE_AUDIO = {"voice", "audio", "voice_note", "ptt", "sound"}

# Respuesta de cortesía cuando el audio no se pudo transcribir. No pasa por el
# agente (no hay query que procesar), se envía directo al lead.
MENSAJE_ERROR_AUDIO = (
    "Disculpa, no pude escuchar bien tu audio 🙏 "
    "¿Me lo podrías repetir o escribirlo por aquí?"
)


class TranscripcionFallida(Exception):
    """El mensaje traía audio pero no se pudo convertir a texto."""


def _parece_nombre_de_audio(valor: str | None) -> bool:
    """True si el string termina en una extensión de audio soportada."""
    if not valor:
        return False
    ruta = urlparse(valor).path if "://" in valor else valor
    return Path(ruta).suffix.lower() in EXTENSIONES_SOPORTADAS


def es_mensaje_de_audio(data: dict) -> bool:
    """
    Determina si el webhook trae una nota de voz o un audio adjunto.

    Se mira primero `attachment[type]` (lo que declara Kommo) y, como respaldo,
    la extensión del link o del nombre de archivo: distintos canales rellenan
    el tipo de forma inconsistente.
    """
    adjunto = data.get("attachment") or {}
    tipo = (adjunto.get("type") or "").strip().lower()

    if tipo in TIPOS_DE_AUDIO:
        return True
    if tipo and tipo not in ("", "file", "document"):
        # picture / video / sticker: adjunto que no es audio.
        return False

    return _parece_nombre_de_audio(adjunto.get("file_name")) or _parece_nombre_de_audio(
        adjunto.get("link")
    )


def obtener_texto_de_entrada(data: dict) -> str:
    """
    Devuelve el texto que se le pasará al agente como query.

    Args:
        data: dict que devuelve `parse_kommo_webhook`.

    Returns:
        El texto escrito por el cliente, o la transcripción de su nota de voz.

    Raises:
        TranscripcionFallida: si el mensaje era audio y no se pudo transcribir
            (sin link, descarga caída, error de la API, o audio en silencio).
    """
    texto = (data.get("text") or "").strip()

    if not es_mensaje_de_audio(data):
        return texto

    adjunto = data.get("attachment") or {}
    link = adjunto.get("link")
    nombre = adjunto.get("file_name")

    if not link:
        raise TranscripcionFallida(
            "El mensaje es de audio pero el webhook no trae `attachment[link]`."
        )

    try:
        transcripcion = transcribir_audio_desde_url(link, nombre)
    except Exception as e:
        raise TranscripcionFallida(f"No se pudo transcribir el audio: {e}") from e

    if not transcripcion:
        raise TranscripcionFallida("La transcripción llegó vacía (¿audio en silencio?).")

    # Si el canal mandó un caption real (no el nombre del archivo), se conserva
    # como contexto adicional para el agente.
    if texto and not _parece_nombre_de_audio(texto) and texto != nombre:
        return f"{transcripcion}\n\n{texto}"

    return transcripcion
