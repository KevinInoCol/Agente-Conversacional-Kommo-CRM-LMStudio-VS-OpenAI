"""
Script para obtener los custom fields de leads en Kommo.
Ejecutar: python get_custom_fields.py
"""

import requests
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración - Puedes cambiar estos valores directamente o usar .env
KOMMO_SUBDOMAIN = os.getenv("KOMMO_SUBDOMAIN") or "teknikkaic"  # Tu subdominio
KOMMO_ACCESS_TOKEN = os.getenv("KOMMO_ACCESS_TOKEN") or ""  # Tu token


def get_custom_fields(entity_type: str = "leads"):
    """
    Obtiene todos los custom fields de un tipo de entidad.
    
    Args:
        entity_type: "leads", "contacts", o "companies"
    """
    if not KOMMO_ACCESS_TOKEN:
        print("❌ Error: KOMMO_ACCESS_TOKEN no está configurado")
        print("   Configúralo en el archivo .env o directamente en este script")
        return
    
    url = f"https://{KOMMO_SUBDOMAIN}.kommo.com/api/v4/{entity_type}/custom_fields"
    
    headers = {
        "Authorization": f"Bearer {KOMMO_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        custom_fields = data.get("_embedded", {}).get("custom_fields", [])
        
        if not custom_fields:
            print(f"No se encontraron custom fields para {entity_type}")
            return
        
        print(f"\n{'='*60}")
        print(f"  CUSTOM FIELDS DE {entity_type.upper()}")
        print(f"  Subdominio: {KOMMO_SUBDOMAIN}")
        print(f"{'='*60}\n")
        
        print(f"{'ID':<12} {'TIPO':<15} {'NOMBRE'}")
        print(f"{'-'*12} {'-'*15} {'-'*30}")
        
        for field in custom_fields:
            field_id = field.get("id", "N/A")
            field_type = field.get("type", "N/A")
            field_name = field.get("name", "Sin nombre")
            
            print(f"{field_id:<12} {field_type:<15} {field_name}")
        
        print(f"\n{'='*60}")
        print(f"  Total: {len(custom_fields)} campos encontrados")
        print(f"{'='*60}\n")
        
        # Mostrar detalles adicionales de campos tipo select/multiselect
        select_fields = [f for f in custom_fields if f.get("type") in ["select", "multiselect"]]
        
        if select_fields:
            print("\n📋 OPCIONES DE CAMPOS SELECT/MULTISELECT:\n")
            for field in select_fields:
                print(f"  Campo: {field.get('name')} (ID: {field.get('id')})")
                enums = field.get("enums", [])
                if enums:
                    for enum in enums:
                        print(f"    - {enum.get('value')} (ID: {enum.get('id')})")
                print()
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ Error HTTP: {e}")
        if response.status_code == 401:
            print("   El token de acceso es inválido o ha expirado")
        elif response.status_code == 403:
            print("   No tienes permisos para acceder a este recurso")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")


def main():
    print("\n🔍 Obteniendo Custom Fields de Kommo...\n")
    
    # Obtener custom fields de leads
    get_custom_fields("leads")
    
    # Descomenta las siguientes líneas si quieres ver campos de contactos o empresas:
    # get_custom_fields("contacts")
    # get_custom_fields("companies")


if __name__ == "__main__":
    main()