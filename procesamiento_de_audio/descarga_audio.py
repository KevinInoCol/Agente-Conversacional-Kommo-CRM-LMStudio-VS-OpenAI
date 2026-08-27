"""
Descarga el archivo de audio que llega adjunto en un webhook de Kommo.

Kommo no manda el audio en el webhook: manda un LINK al archivo alojado en su
CDN. Este módulo baja ese archivo a un temporal del sistema con una extensión
que la API de Whisper acepte, valida el tamaño y lo entrega como `Path`.

Notas:
- Los audios de WhatsApp/Telegram llegan casi siempre como .ogg (codec opus),
  que Whisper soporta nativamente. No hace falta ffmpeg ni conversión.
- Algunos links de Kommo son públicos y otros exigen el Bearer token de la
  cuenta; por eso, ante un 401/403 se reintenta con `KOMMO_ACCESS_TOKEN`.
- El archivo temporal NO se borra solo: usa el context manager `audio_temporal`
  para garantizar la limpieza.

Prueba manual:
    python procesamiento_de_audio/descarga_audio.py "https://.../audio.ogg"
"""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import requests

from dotenv import load_dotenv

load_dotenv()

KOMMO_ACCESS_TOKEN = os.getenv("KOMMO_ACCESS_TOKEN")

# Formatos que acepta la API de transcripción de OpenAI (Whisper).
EXTENSIONES_SOPORTADAS = {
    ".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm",
}

# Fallback cuando la URL no trae extensión: se deduce del Content-Type.
MIME_A_EXTENSION = {
    "audio/ogg": ".ogg",
    "audio/opus": ".ogg",
    "audio/oga": ".oga",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
    "audio/aac": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/webm": ".webm",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}

EXTENSION_POR_DEFECTO = ".ogg"          # lo que manda WhatsApp vía Kommo
LIMITE_MB = float(os.getenv("AUDIO_MAX_MB", "25"))   # tope duro de la API de OpenAI
TIMEOUT_SEGUNDOS = int(os.getenv("AUDIO_DOWNLOAD_TIMEOUT", "30"))
TAMANO_CHUNK_BYTES = 64 * 1024


def _extension_desde_nombre(nombre: str | None) -> str | None:
    """Extrae una extensión soportada desde un nombre de archivo o una URL."""
    if not nombre:
        return None
    ruta = urlparse(nombre).path if "://" in nombre else nombre
    sufijo = Path(ruta).suffix.lower()
    return sufijo if sufijo in EXTENSIONES_SOPORTADAS else None


def _extension_desde_content_type(content_type: str | None) -> str | None:
    """Deduce la extensión a partir del header Content-Type de la respuesta."""
    if not content_type:
        return None
    mime = content_type.split(";")[0].strip().lower()
    return MIME_A_EXTENSION.get(mime)


def _abrir_stream(url: str) -> requests.Response:
    """
    GET en streaming. Primero anónimo (los links de CDN suelen ser públicos) y,
    si Kommo responde 401/403, se reintenta firmando con el access token.
    """
    respuesta = requests.get(url, stream=True, timeout=TIMEOUT_SEGUNDOS)

    if respuesta.status_code in (401, 403) and KOMMO_ACCESS_TOKEN:
        respuesta.close()
        respuesta = requests.get(
            url,
            stream=True,
            timeout=TIMEOUT_SEGUNDOS,
            headers={"Authorization": f"Bearer {KOMMO_ACCESS_TOKEN}"},
        )

    respuesta.raise_for_status()
    return respuesta


def descargar_audio(url: str, nombre_archivo: str | None = None) -> Path:
    """
    Descarga el audio de `url` a un archivo temporal y devuelve su ruta.

    Args:
        url: link del adjunto (viene en el webhook de Kommo).
        nombre_archivo: nombre original del adjunto, si el webhook lo trae.
            Solo se usa para adivinar la extensión.

    Returns:
        Path del archivo temporal descargado. Es responsabilidad de quien llama
        borrarlo (o usar `audio_temporal`).

    Raises:
        ValueError: si la URL está vacía o el audio supera LIMITE_MB.
        requests.HTTPError: si la descarga falla.
    """
    if not url:
        raise ValueError("No se recibió URL de audio para descargar.")

    respuesta = _abrir_stream(url)

    extension = (
        _extension_desde_nombre(nombre_archivo)
        or _extension_desde_nombre(url)
        or _extension_desde_content_type(respuesta.headers.get("Content-Type"))
        or EXTENSION_POR_DEFECTO
    )

    limite_bytes = int(LIMITE_MB * 1024 * 1024)
    descargados = 0

    temporal = tempfile.NamedTemporaryFile(suffix=extension, delete=False)
    ruta = Path(temporal.name)

    try:
        with temporal, respuesta:
            for bloque in respuesta.iter_content(chunk_size=TAMANO_CHUNK_BYTES):
                if not bloque:
                    continue
                descargados += len(bloque)
                if descargados > limite_bytes:
                    raise ValueError(
                        f"El audio supera el límite de {LIMITE_MB} MB "
                        f"admitido por la API de transcripción."
                    )
                temporal.write(bloque)
    except Exception:
        ruta.unlink(missing_ok=True)
        raise

    print(f"🎧 Audio descargado: {ruta.name} ({descargados / 1024:.1f} KB)")
    return ruta


@contextmanager
def audio_temporal(url: str, nombre_archivo: str | None = None):
    """
    Context manager: descarga el audio y borra el temporal al salir del bloque,
    pase lo que pase.

        with audio_temporal(link) as ruta:
            texto = transcribir_audio(ruta)
    """
    ruta = descargar_audio(url, nombre_archivo)
    try:
        yield ruta
    finally:
        ruta.unlink(missing_ok=True)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python procesamiento_de_audio/descarga_audio.py <url_del_audio>")
        sys.exit(1)

    destino = descargar_audio(sys.argv[1])
    print(f"✅ Guardado en: {destino}")
