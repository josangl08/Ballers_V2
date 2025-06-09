# controllers/google_client.py
"""
Cliente para APIs de Google simplificado.
Usa configuración unificada de config.py.
"""
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
from config import GOOGLE_CREDENTIALS, GOOGLE_SA_PATH, IS_PRODUCTION

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

def _get_credentials():
    """Obtiene credenciales de Google desde config unificado."""
    
    if IS_PRODUCTION:
        # Producción: usar GOOGLE_CREDENTIALS de secrets
        if GOOGLE_CREDENTIALS:
            print("🔑 Usando credenciales de Google desde Streamlit secrets")
            return Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
        else:
            raise RuntimeError(
                "No se pudieron obtener credenciales de Google desde secrets. "
                "Verifica la configuración en Streamlit Cloud."
            )
    else:
        # Desarrollo: usar archivo local
        if GOOGLE_SA_PATH and os.path.exists(GOOGLE_SA_PATH):
            print(f"🔑 Usando credenciales de Google desde archivo: {GOOGLE_SA_PATH}")
            return Credentials.from_service_account_file(GOOGLE_SA_PATH, scopes=SCOPES)
        else:
            raise RuntimeError(
                f"Archivo de credenciales no encontrado: {GOOGLE_SA_PATH}. "
                "Verifica que el archivo exista en desarrollo."
            )

def calendar():
    """Cliente de Google Calendar."""
    return build("calendar", "v3", credentials=_get_credentials(), cache_discovery=False)

def sheets():
    """Cliente de Google Sheets."""
    return build("sheets", "v4", credentials=_get_credentials(), cache_discovery=False)