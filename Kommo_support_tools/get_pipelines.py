"""
Script para obtener los pipelines y sus etapas en Kommo.
Ejecutar: python get_pipelines.py
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

KOMMO_SUBDOMAIN = os.getenv("KOMMO_SUBDOMAIN") or "teknikkaic"
KOMMO_ACCESS_TOKEN = os.getenv("KOMMO_ACCESS_TOKEN") or ""


def get_pipelines():
    """Obtiene todos los pipelines de leads y sus etapas (stages)."""
    if not KOMMO_ACCESS_TOKEN:
        print("❌ Error: KOMMO_ACCESS_TOKEN no está configurado")
        return

    url = f"https://{KOMMO_SUBDOMAIN}.kommo.com/api/v4/leads/pipelines"

    headers = {
        "Authorization": f"Bearer {KOMMO_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        pipelines = data.get("_embedded", {}).get("pipelines", [])

        if not pipelines:
            print("No se encontraron pipelines")
            return

        print(f"\n{'='*60}")
        print(f"  PIPELINES DE LEADS")
        print(f"  Subdominio: {KOMMO_SUBDOMAIN}")
        print(f"{'='*60}\n")

        for pipeline in pipelines:
            pipeline_id = pipeline.get("id")
            pipeline_name = pipeline.get("name", "Sin nombre")
            is_main = pipeline.get("is_main", False)

            marker = " (PRINCIPAL)" if is_main else ""
            print(f"📋 Pipeline: {pipeline_name}{marker}")
            print(f"   ID: {pipeline_id}")

            stages = pipeline.get("_embedded", {}).get("statuses", [])
            if stages:
                print(f"   Etapas:")
                for stage in stages:
                    stage_id = stage.get("id")
                    stage_name = stage.get("name", "Sin nombre")
                    stage_color = stage.get("color", "")
                    print(f"     - {stage_name} (ID: {stage_id}) {stage_color}")

            print()

        print(f"{'='*60}")
        print(f"  Total: {len(pipelines)} pipelines encontrados")
        print(f"{'='*60}\n")

    except requests.exceptions.HTTPError as e:
        print(f"❌ Error HTTP: {e}")
        if response.status_code == 401:
            print("   El token de acceso es inválido o ha expirado")
        elif response.status_code == 403:
            print("   No tienes permisos para acceder a este recurso")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")


if __name__ == "__main__":
    print("\n🔍 Obteniendo Pipelines de Kommo...\n")
    get_pipelines()
