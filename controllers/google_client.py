# controllers/google_client.py
"""
Cliente para APIs de Google - SIMPLIFICADO
"""
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
import json
from config import GOOGLE_CREDENTIALS, GOOGLE_SA_PATH, IS_PRODUCTION

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

def _get_credentials():
    """Obtiene credenciales de Google de forma simple y robusta."""
    
    try:
        if IS_PRODUCTION:
            # Producción: usar credenciales desde config
            if GOOGLE_CREDENTIALS:
                print("🔑 Usando credenciales de Google desde secrets")
                # Asegurar que la private_key tenga saltos de línea correctos
                creds_dict = GOOGLE_CREDENTIALS.copy()
                if 'private_key' in creds_dict:
                    creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
                return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            else:
                raise ValueError("GOOGLE_CREDENTIALS no disponible en producción")
        else:
            # Desarrollo: usar archivo local
            if GOOGLE_SA_PATH and os.path.exists(GOOGLE_SA_PATH):
                print(f"🔑 Usando credenciales desde archivo: {GOOGLE_SA_PATH}")
                return Credentials.from_service_account_file(GOOGLE_SA_PATH, scopes=SCOPES)
            else:
                raise ValueError(f"Archivo de credenciales no encontrado: {GOOGLE_SA_PATH}")
                
    except Exception as e:
        print(f"❌ Error obteniendo credenciales: {e}")
        # Intentar debug detallado
        if IS_PRODUCTION and GOOGLE_CREDENTIALS:
            print("🔍 Debug - Claves disponibles:", list(GOOGLE_CREDENTIALS.keys()) if GOOGLE_CREDENTIALS else "None")
        raise

def calendar():
    """Cliente de Google Calendar."""
    return build("calendar", "v3", credentials=_get_credentials(), cache_discovery=False)

def sheets():
    """Cliente de Google Sheets."""
    return build("sheets", "v4", credentials=_get_credentials(), cache_discovery=False)