# controllers/google_client.py
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
import streamlit as st
import tempfile
import json

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

def _creds():
    """Obtiene credenciales desde Streamlit secrets o archivo local"""
    
    # 1. Intentar desde Streamlit secrets (Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and hasattr(st.secrets, 'google'):
            print("🔑 Usando credenciales de Google desde Streamlit secrets")
            
            # Construir dict de credenciales desde secrets
            cred_dict = {
                "type": st.secrets.google.type,
                "project_id": st.secrets.google.project_id,
                "private_key_id": st.secrets.google.private_key_id,
                "private_key": st.secrets.google.private_key,
                "client_email": st.secrets.google.client_email,
                "client_id": st.secrets.google.client_id,
                "auth_uri": st.secrets.google.auth_uri,
                "token_uri": st.secrets.google.token_uri,
                "auth_provider_x509_cert_url": st.secrets.google.auth_provider_x509_cert_url,
                "client_x509_cert_url": st.secrets.google.client_x509_cert_url,
                "universe_domain": st.secrets.google.universe_domain
            }
            
            return Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
            
    except Exception as e:
        print(f"⚠️ No se pudieron leer credenciales de secrets: {e}")
    
    # 2. Fallback: archivo local (desarrollo)
    google_sa_path = os.getenv("GOOGLE_SA_PATH", "data/google_service_account.json")
    if os.path.exists(google_sa_path):
        print(f"🔑 Usando credenciales de Google desde archivo: {google_sa_path}")
        return Credentials.from_service_account_file(google_sa_path, scopes=SCOPES)
    
    # 3. Error si no se encuentra ninguna credencial
    raise RuntimeError(
        "No se pudieron encontrar credenciales de Google. "
        "Verifica que estén configuradas en Streamlit secrets o en el archivo local."
    )

def calendar():
    return build("calendar", "v3", credentials=_creds(), cache_discovery=False)

def sheets():
    return build("sheets", "v4", credentials=_creds(), cache_discovery=False)