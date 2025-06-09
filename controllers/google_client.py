# controllers/google_client.py
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os

# 🆕 NUEVO: Importar configuración de producción
from config_production import ProductionConfig, IS_PRODUCTION, IS_DEVELOPMENT

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

def _creds():
    """
    Obtiene credenciales de Google adaptándose al entorno.
    
    Returns:
        Credentials: Credenciales de Google configuradas
    """
    if IS_PRODUCTION:
        # En producción: usar secrets de Streamlit Cloud
        credentials_dict = ProductionConfig.get_google_credentials()
        return Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
    else:
        # En desarrollo: usar archivo local
        google_sa_path = ProductionConfig.get_google_sa_path()
        if not google_sa_path or not os.path.exists(google_sa_path):
            raise FileNotFoundError(
                f"Google service account file not found: {google_sa_path}\n"
                "Make sure the file exists and the path is correct in your .env file."
            )
        return Credentials.from_service_account_file(google_sa_path, scopes=SCOPES)

def calendar():
    """
    Crea cliente de Google Calendar.
    
    Returns:
        Resource: Cliente de Google Calendar API
    """
    try:
        return build("calendar", "v3", credentials=_creds(), cache_discovery=False)
    except Exception as e:
        env_type = "production (Streamlit Secrets)" if IS_PRODUCTION else "development (local file)"
        raise Exception(f"Error creating Google Calendar client in {env_type}: {str(e)}")

def sheets():
    """
    Crea cliente de Google Sheets.
    
    Returns:
        Resource: Cliente de Google Sheets API
    """
    try:
        return build("sheets", "v4", credentials=_creds(), cache_discovery=False)
    except Exception as e:
        env_type = "production (Streamlit Secrets)" if IS_PRODUCTION else "development (local file)"
        raise Exception(f"Error creating Google Sheets client in {env_type}: {str(e)}")

def test_google_apis() -> dict:
    """
    Prueba la conexión a las APIs de Google.
    
    Returns:
        dict: Resultado de las pruebas
    """
    results = {
        "calendar_api": False,
        "sheets_api": False,
        "calendar_id": ProductionConfig.get_calendar_id(),
        "sheets_id": ProductionConfig.get_accounting_sheet_id(),
        "environment": "PRODUCTION" if IS_PRODUCTION else "DEVELOPMENT"
    }
    
    # Probar Calendar API
    try:
        cal_service = calendar()
        # Intentar listar calendarios como prueba
        cal_service.calendarList().list().execute()
        results["calendar_api"] = True
        print("✅ Google Calendar API connection successful")
    except Exception as e:
        print(f"❌ Google Calendar API error: {e}")
        results["calendar_error"] = str(e)
    
    # Probar Sheets API
    try:
        sheets_service = sheets()
        sheets_id = ProductionConfig.get_accounting_sheet_id()
        # Intentar leer una celda como prueba
        sheets_service.spreadsheets().values().get(
            spreadsheetId=sheets_id, 
            range="A1:A1"
        ).execute()
        results["sheets_api"] = True
        print("✅ Google Sheets API connection successful")
    except Exception as e:
        print(f"❌ Google Sheets API error: {e}")
        results["sheets_error"] = str(e)
    
    return results