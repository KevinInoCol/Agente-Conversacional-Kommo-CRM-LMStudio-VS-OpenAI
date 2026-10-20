"""
Tool `gsheets_buscar_inmuebles`: consulta el INVENTARIO de inmuebles disponibles desde un
Google Sheets y lo expone como una tool de LangChain (`create_agent`).

Es la ÚNICA fuente de verdad del inventario (a diferencia de `busqueda_en_base_conocimiento`,
que cubre políticas/FAQ vía RAG). Es una tool COMPARTIDA entre todos los leads
(no depende del lead_id), igual que `busqueda_en_base_conocimiento`.

Acceso al Sheet
---------------
Vía cuenta de servicio de Google (gspread + google-auth). Configuración por .env:
- GOOGLE_SERVICE_ACCOUNT_FILE → ruta al JSON de la service account (ej: ./service_account.json)
    (alternativa para despliegue: GOOGLE_SERVICE_ACCOUNT_JSON con el JSON inline)
- GOOGLE_SHEET_URL            → URL completa de la hoja
    (alternativa: GOOGLE_SHEET_ID con solo el id)
- GOOGLE_SHEET_WORKSHEET      → (opcional) nombre de la pestaña; por defecto la primera

IMPORTANTE: la hoja debe estar COMPARTIDA con el email de la service account
(client_email dentro del JSON), aunque sea con permiso de solo lectura.

Estructura esperada de columnas (fila 1 = encabezados). El matcheo es tolerante
a mayúsculas/acentos/espacios y admite alias, así que no importa el orden exacto:
    ID · Tipo · Barrio · Dirección · Metros Cuadrados · Habitaciones · Baños ·
    Cocheras · Alquiler Mensual (BRL) · IPTU Mensual (BRL) · Agua/SANASA ·
    Estado Amoblado
"""

import json
import os
import unicodedata

import gspread
from google.oauth2.service_account import Credentials
from langchain.tools import tool

# Solo lectura: no necesitamos permisos de escritura sobre el Sheet.
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Cuántos inmuebles devolver como máximo por consulta (el LLM presenta 3-4).
_MAX_RESULTS = 12


# ──────────────────────────────────────────────
# Normalización y mapa de columnas (tolerante a alias)
# ──────────────────────────────────────────────

def _norm(text: str) -> str:
    """minúsculas, sin acentos, sin espacios/puntuación → para comparar encabezados."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "".join(c for c in text.lower() if c.isalnum())

# Campo canónico → alias posibles del encabezado en el Sheet.
_COLUMN_ALIASES = {
    "id":            ["id", "codigo", "código", "ref", "referencia"],
    "tipo":          ["tipo", "tipoinmueble", "tipodeinmueble"],
    "barrio":        ["barrio", "bairro", "zona", "sector"],
    "direccion":     ["direccion", "dirección", "endereco", "endereço", "address"],
    "metros":        ["metroscuadrados", "m2", "metros", "area", "área", "metragem"],
    "habitaciones":  ["habitaciones", "quartos", "dormitorios", "dormitórios", "recamaras", "cuartos"],
    "banos":         ["banos", "baños", "banheiros", "banheiro"],
    "cocheras":      ["cocheras", "vagas", "garagem", "estacionamiento", "garaje"],
    "alquiler":      ["alquilermensual", "alquilermensualbrl", "alquiler", "aluguel", "renta", "precio"],
    "iptu":          ["iptumensual", "iptumensualbrl", "iptu"],
    "agua":          ["aguasanasa", "agua", "sanasa"],
    "amoblado":      ["estadoamoblado", "amoblado", "amueblado", "mobiliado", "amoblamiento"],
}


def _build_alias_index() -> dict:
    """alias_normalizado → campo canónico."""
    idx = {}
    for canon, aliases in _COLUMN_ALIASES.items():
        for a in aliases:
            idx[_norm(a)] = canon
    return idx

_ALIAS_INDEX = _build_alias_index()


def _canonize_row(row: dict) -> dict:
    """Convierte una fila cruda del Sheet a claves canónicas conocidas."""
    out = {}
    for raw_key, value in row.items():
        canon = _ALIAS_INDEX.get(_norm(raw_key))
        if canon:
            out[canon] = value
    return out


def _to_number(value) -> float | None:
    """Extrae un número de valores como 'R$ 1.500,00', '1500', '80 m²'."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Quita todo menos dígitos, coma, punto y signo.
    cleaned = "".join(c for c in s if c.isdigit() or c in ".,-")
    if not cleaned:
        return None
    # Formato brasileño "1.500,00" → "1500.00". Si hay coma decimal, punto = miles.
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _truthy(value) -> bool:
    return _norm(value) in {"si", "sí", "yes", "true", "1", "x", "amoblado", "amueblado", "mobiliado"}


# ──────────────────────────────────────────────
# Conexión al Sheet (worksheet cacheado)
# ──────────────────────────────────────────────

_worksheet = None


def _get_credentials() -> Credentials:
    inline = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if inline:
        info = json.loads(inline)
        return Credentials.from_service_account_info(info, scopes=_SCOPES)

    path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not path:
        raise ValueError(
            "Falta la credencial de Google: define GOOGLE_SERVICE_ACCOUNT_FILE "
            "(ruta al JSON) o GOOGLE_SERVICE_ACCOUNT_JSON (JSON inline) en el .env."
        )
    if not os.path.isabs(path):
        # Rutas relativas → respecto a la raíz del proyecto.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(project_root, path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró el JSON de la service account: {path}")
    return Credentials.from_service_account_file(path, scopes=_SCOPES)


def _get_worksheet():
    """Abre (una vez) la pestaña del Google Sheet configurado."""
    global _worksheet
    if _worksheet is not None:
        return _worksheet

    gc = gspread.authorize(_get_credentials())

    url = os.getenv("GOOGLE_SHEET_URL")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if url:
        spreadsheet = gc.open_by_url(url)
    elif sheet_id:
        spreadsheet = gc.open_by_key(sheet_id)
    else:
        raise ValueError(
            "Falta la hoja: define GOOGLE_SHEET_URL o GOOGLE_SHEET_ID en el .env."
        )

    worksheet_name = os.getenv("GOOGLE_SHEET_WORKSHEET")
    _worksheet = (
        spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1
    )
    return _worksheet


def _load_inmuebles() -> list[dict]:
    """Lee todas las filas del Sheet y las devuelve canonizadas (una por inmueble)."""
    ws = _get_worksheet()
    raw_rows = ws.get_all_records()  # usa la fila 1 como encabezados
    return [_canonize_row(r) for r in raw_rows]


# ──────────────────────────────────────────────
# Filtrado + formato de resultados
# ──────────────────────────────────────────────

def _matches(inm: dict, tipo, barrio, alquiler_max,
             habitaciones_min, banos_min, cocheras_min, amoblado) -> bool:
    if tipo and _norm(tipo) not in _norm(inm.get("tipo", "")):
        return False
    if barrio and _norm(barrio) not in _norm(inm.get("barrio", "")):
        return False
    if alquiler_max and alquiler_max > 0:
        precio = _to_number(inm.get("alquiler"))
        if precio is None or precio > alquiler_max:
            return False
    if habitaciones_min and habitaciones_min > 0:
        h = _to_number(inm.get("habitaciones"))
        if h is None or h < habitaciones_min:
            return False
    if banos_min and banos_min > 0:
        b = _to_number(inm.get("banos"))
        if b is None or b < banos_min:
            return False
    if cocheras_min and cocheras_min > 0:
        c = _to_number(inm.get("cocheras"))
        if c is None or c < cocheras_min:
            return False
    if amoblado:
        quiere = _truthy(amoblado)
        tiene = _truthy(inm.get("amoblado"))
        if quiere != tiene:
            return False
    return True


def _format_inmueble(inm: dict) -> str:
    """Formatea un inmueble de forma legible para el LLM."""
    campos = [
        ("ID", inm.get("id")),
        ("Tipo", inm.get("tipo")),
        ("Barrio", inm.get("barrio")),
        ("Dirección", inm.get("direccion")),
        ("m²", inm.get("metros")),
        ("Habitaciones", inm.get("habitaciones")),
        ("Baños", inm.get("banos")),
        ("Cocheras", inm.get("cocheras")),
        ("Alquiler (R$)", inm.get("alquiler")),
        ("IPTU (R$)", inm.get("iptu")),
        ("Agua/SANASA", inm.get("agua")),
        ("Amoblado", inm.get("amoblado")),
    ]
    partes = [f"{k}: {v}" for k, v in campos if v not in (None, "")]
    return " | ".join(partes)


def get_buscar_inmuebles_tool():
    """
    Factory que devuelve la tool `gsheets_buscar_inmuebles` de LangChain.
    Es una tool compartida (no depende del lead_id). Se construye una sola vez en
    `init_resources` (agent.py). Al invocarla se valida la conexión al Sheet.
    """
    # Validación temprana de conexión (falla claro al arrancar, no en pleno request).
    _get_worksheet()

    @tool
    def gsheets_buscar_inmuebles(
        tipo: str = "",
        barrio: str = "",
        alquiler_max: float = 0,
        habitaciones_min: int = 0,
        banos_min: int = 0,
        cocheras_min: int = 0,
        amoblado: str = "",
    ) -> str:
        """Consulta el inventario de inmuebles disponibles en alquiler (Alpha State).
        ÚNICA fuente de verdad del inventario. Úsala cuando el cliente busque inmuebles
        por criterios o pregunte por uno específico. Todos los argumentos son OPCIONALES
        (filtros); omite los que el cliente no mencione.

        Args:
            tipo: Casa, Departamento o Kitnet.
            barrio: barrio/zona (ej: 'Barão Geraldo', 'Cidade Universitária').
            alquiler_max: alquiler mensual máximo en reales (R$). 0 = sin tope.
            habitaciones_min: mínimo de habitaciones. 0 = indiferente.
            banos_min: mínimo de baños. 0 = indiferente.
            cocheras_min: mínimo de cocheras. 0 = indiferente.
            amoblado: 'sí' o 'no' para filtrar por amoblado; vacío = indiferente.

        Devuelve los inmuebles que cumplen los criterios (montos en R$).
        """
        inmuebles = _load_inmuebles()
        if not inmuebles:
            return "El inventario está vacío o no se pudo leer la hoja de inmuebles."

        encontrados = [
            inm for inm in inmuebles
            if _matches(inm, tipo, barrio, alquiler_max,
                        habitaciones_min, banos_min, cocheras_min, amoblado)
        ]

        if not encontrados:
            return (
                "No hay inmuebles disponibles que cumplan esos criterios. "
                "Sugiere al cliente ampliar el presupuesto, la zona o el tipo."
            )

        recortados = encontrados[:_MAX_RESULTS]
        cabecera = f"{len(encontrados)} inmueble(s) disponibles"
        if len(encontrados) > _MAX_RESULTS:
            cabecera += f" (mostrando los primeros {_MAX_RESULTS})"
        cuerpo = "\n\n---\n\n".join(_format_inmueble(inm) for inm in recortados)
        return f"{cabecera}:\n\n{cuerpo}"

    return gsheets_buscar_inmuebles
