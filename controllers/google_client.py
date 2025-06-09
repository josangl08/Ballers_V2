# controllers/google_client.py
"""
Cliente para APIs de Google con detección corregida de entorno.
"""
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
from config import GOOGLE_CREDENTIALS, GOOGLE_SA_PATH, IS_PRODUCTION, IS_DEVELOPMENT

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

def _get_credentials():
    """
    Obtiene credenciales de Google con detección corregida de entorno.
    """
    
    # DESARROLLO: Usar archivo local PRIMERO
    if IS_DEVELOPMENT:
        if GOOGLE_SA_PATH and os.path.exists(GOOGLE_SA_PATH):
            try:
                print(f"🔑 Usando credenciales de Google desde archivo: {GOOGLE_SA_PATH}")
                return Credentials.from_service_account_file(GOOGLE_SA_PATH, scopes=SCOPES)
            except Exception as e:
                print(f"❌ Error leyendo archivo local: {e}")
                raise RuntimeError(f"❌ DESARROLLO: Error con archivo {GOOGLE_SA_PATH}: {e}")
        else:
            raise RuntimeError(
                f"❌ DESARROLLO: Archivo de credenciales no encontrado: {GOOGLE_SA_PATH}\n"
                "Verifica que el archivo exista y tenga permisos correctos."
            )
    
    # PRODUCCIÓN: Usar secrets de Streamlit
    else:
        # Método 1: GOOGLE_CREDENTIALS de config (desde secrets)
        if GOOGLE_CREDENTIALS:
            try:
                print("🔑 Usando credenciales de Google desde Streamlit secrets")
                return Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
            except Exception as e:
                print(f"❌ Error con GOOGLE_CREDENTIALS: {e}")
        
        # Método 2: Intentar leer secrets directamente (por si config falló)
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and hasattr(st.secrets, 'google'):
                cred_dict = {
                    "type": st.secrets["google"]["type"],
                    "project_id": st.secrets["google"]["project_id"],
                    "private_key_id": st.secrets["google"]["private_key_id"],
                    "private_key": st.secrets["google"]["private_key"],
                    "client_email": st.secrets["google"]["client_email"],
                    "client_id": st.secrets["google"]["client_id"],
                    "auth_uri": st.secrets["google"]["auth_uri"],
                    "token_uri": st.secrets["google"]["token_uri"],
                    "auth_provider_x509_cert_url": st.secrets["google"]["auth_provider_x509_cert_url"],
                    "client_x509_cert_url": st.secrets["google"]["client_x509_cert_url"],
                    "universe_domain": st.secrets["google"]["universe_domain"]
                }
                print("🔑 Usando credenciales de Google desde secrets directos")
                return Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
        except Exception as e:
            print(f"❌ Error con secrets directos: {e}")
        
        # Si llegamos aquí, todos los métodos de producción fallaron
        raise RuntimeError(
            "❌ PRODUCCIÓN: No se pudieron obtener credenciales de Google.\n"
            "Verifica que los secrets estén configurados correctamente en Streamlit Cloud.\n"
            "Secrets necesarios: google.type, google.project_id, google.private_key, etc."
        )

def calendar():
    """Cliente de Google Calendar."""
    try:
        return build("calendar", "v3", credentials=_get_credentials(), cache_discovery=False)
    except Exception as e:
        print(f"❌ Error creando cliente de Calendar: {e}")
        raise

def sheets():
    """Cliente de Google Sheets."""
    try:
        return build("sheets", "v4", credentials=_get_credentials(), cache_discovery=False)
    except Exception as e:
        print(f"❌ Error creando cliente de Sheets: {e}")
        raise