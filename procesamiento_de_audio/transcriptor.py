"""
Transcripción de audio a texto con Whisper (API de OpenAI).

Convierte una nota de voz en la query de texto que consume el agente. Se usa
SIEMPRE la API de OpenAI (`whisper-1`), aunque el LLM del agente esté corriendo
en LM Studio: la transcripción es un servicio aparte y no depende de
LLM_PROVIDER.

El cliente de OpenAI se crea perezosamente (singleton de módulo) para que
importar este archivo no falle si aún no se cargó OPENAI_API_KEY.

Prueba manual:
    python procesamiento_de_audio/transcriptor.py Base_de_Conocimiento/nota.ogg
"""

import os
from pathlib import Path

from openai import OpenAI

from dotenv import load_dotenv

try:  # import normal cuando se usa como paquete (app.py, agente)
    from procesamiento_de_audio.descarga_audio import audio_temporal
except ImportError:  # ejecución directa: python procesamiento_de_audio/transcriptor.py
    from descarga_audio import audio_temporal

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

MODELO_WHISPER = os.getenv("WHISPER_MODEL", "whisper-1")
# Fijar el idioma mejora precisión y latencia; vacío = autodetección.
IDIOMA_WHISPER = os.getenv("WHISPER_LANGUAGE", "es")
# Pista de vocabulario (nombres de marca, jerga del negocio) para reducir errores.
PROMPT_WHISPER = os.getenv("WHISPER_PROMPT", "")

_cliente: OpenAI | None = None


def _get_cliente() -> OpenAI:
    """Devuelve el cliente de OpenAI, creándolo la primera vez que se usa."""
    global _cliente
    if _cliente is None:
        if not OPENAI_API_KEY:
            raise RuntimeError(
                "Falta OPENAI_API_KEY en el .env: es obligatoria para transcribir "
                "audio con Whisper, incluso si LLM_PROVIDER=lmstudio."
            )
        _cliente = OpenAI(api_key=OPENAI_API_KEY)
    return _cliente


def transcribir_audio(
    ruta_audio: str | Path,
    idioma: str | None = None,
    prompt: str | None = None,
) -> str:
    """
    Transcribe un archivo de audio local y devuelve el texto plano.

    Args:
        ruta_audio: ruta al archivo (.ogg, .mp3, .m4a, .wav, .webm, ...).
        idioma: código ISO-639-1 ("es", "en"). Por defecto WHISPER_LANGUAGE.
            Pasar cadena vacía fuerza la autodetección de Whisper.
        prompt: pista de vocabulario opcional. Por defecto WHISPER_PROMPT.

    Returns:
        El texto transcrito, ya limpio de espacios sobrantes.

    Raises:
        FileNotFoundError: si el archivo no existe.
        RuntimeError: si falta OPENAI_API_KEY.
    """
    ruta = Path(ruta_audio)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo de audio: {ruta}")

    idioma_final = IDIOMA_WHISPER if idioma is None else idioma
    prompt_final = PROMPT_WHISPER if prompt is None else prompt

    parametros = {"model": MODELO_WHISPER, "response_format": "text"}
    if idioma_final:
        parametros["language"] = idioma_final
    if prompt_final:
        parametros["prompt"] = prompt_final

    print(f"📝 Transcribiendo con {MODELO_WHISPER} ({ruta.name})...")

    with ruta.open("rb") as archivo:
        # response_format="text" devuelve directamente un str, no un objeto.
        resultado = _get_cliente().audio.transcriptions.create(file=archivo, **parametros)

    texto = (resultado if isinstance(resultado, str) else resultado.text).strip()
    print(f"🗣️ Transcripción: '{texto[:80]}...'" if len(texto) > 80 else f"🗣️ Transcripción: '{texto}'")
    return texto


def transcribir_audio_desde_url(url: str, nombre_archivo: str | None = None) -> str:
    """
    Descarga un audio remoto (link del adjunto de Kommo) y lo transcribe.
    El archivo temporal se borra siempre, incluso si la transcripción falla.
    """
    with audio_temporal(url, nombre_archivo) as ruta:
        return transcribir_audio(ruta)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python procesamiento_de_audio/transcriptor.py <ruta_o_url_del_audio>")
        sys.exit(1)

    entrada = sys.argv[1]
    salida = (
        transcribir_audio_desde_url(entrada)
        if entrada.startswith(("http://", "https://"))
        else transcribir_audio(entrada)
    )
    print("\n--- TEXTO ---")
    print(salida)
