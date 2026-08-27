"""
Procesamiento de audio de entrada: nota de voz de Kommo → texto para el agente.

Módulos:
- `descarga_audio`: baja el adjunto del CDN de Kommo a un temporal (con límite
  de tamaño y limpieza garantizada).
- `transcriptor`:   llama a Whisper (API de OpenAI) y devuelve el texto.
- `procesador`:     decide si el webhook trae texto o audio y entrega la query
                    final del agente (`obtener_texto_de_entrada`).

Uso desde app.py:

    from procesamiento_de_audio import obtener_texto_de_entrada, TranscripcionFallida

    texto = obtener_texto_de_entrada(data)   # data = parse_kommo_webhook(body)
"""

from procesamiento_de_audio.descarga_audio import audio_temporal, descargar_audio
from procesamiento_de_audio.procesador import (
    MENSAJE_ERROR_AUDIO,
    TranscripcionFallida,
    es_mensaje_de_audio,
    obtener_texto_de_entrada,
)
from procesamiento_de_audio.transcriptor import (
    transcribir_audio,
    transcribir_audio_desde_url,
)

__all__ = [
    "audio_temporal",
    "descargar_audio",
    "transcribir_audio",
    "transcribir_audio_desde_url",
    "es_mensaje_de_audio",
    "obtener_texto_de_entrada",
    "TranscripcionFallida",
    "MENSAJE_ERROR_AUDIO",
]
