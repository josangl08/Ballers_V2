# config_production.py
"""
Configuración específica para producción.
Maneja las diferencias entre desarrollo (local) y producción (Streamlit Cloud + Supabase).
"""
import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

# Detectar si estamos en Streamlit Cloud
def is_streamlit_cloud():
    """Detecta si la aplicación está ejecutándose en Streamlit Cloud."""
    return (
        "STREAMLIT_SHARING" in os.environ or 
        "STREAMLIT_CLOUD" in os.environ or
        os.getenv("STREAMLIT_SERVER_PORT") is not None
    )

# Detectar entorno
IS_PRODUCTION = is_streamlit_cloud()
IS_DEVELOPMENT = not IS_PRODUCTION

class ProductionConfig:
    """
    Configuración para producción.
    Obtiene variables de Streamlit Secrets en lugar de archivos locales.
    """
    
    @staticmethod
    def get_database_url():
        """Obtiene URL de base de datos desde secrets de Streamlit Cloud."""
        if IS_PRODUCTION:
            # En producción: construir URL desde secrets de Streamlit Cloud
            return (
                f"postgresql://{st.secrets['database']['username']}:"
                f"{st.secrets['database']['password']}@"
                f"{st.secrets['database']['host']}:"
                f"{st.secrets['database']['port']}/"
                f"{st.secrets['database']['database']}"
            )
        else:
            # En desarrollo: usar SQLite local
            return f"sqlite:///{os.getenv('DATABASE_PATH', 'data/ballers_app.db')}"
    
    @staticmethod
    def get_google_credentials():
        """Obtiene credenciales de Google desde secrets o archivo local."""
        if IS_PRODUCTION:
            # En producción: usar secrets de Streamlit Cloud
            return {
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
        else:
            # En desarrollo: usar archivo local
            return None  # Se usa el archivo local normal
    
    @staticmethod
    def get_google_sa_path():
        """Obtiene ruta de credenciales de Google."""
        if IS_PRODUCTION:
            # En producción: no hay archivo, se usan secrets directamente
            return None
        else:
            # En desarrollo: usar archivo local
            return os.getenv("GOOGLE_SA_PATH", "data/google_service_account.json")
    
    @staticmethod
    def get_calendar_id():
        """Obtiene ID del calendario."""
        if IS_PRODUCTION:
            return st.secrets["google"]["calendar_id"]
        else:
            return os.getenv("CALENDAR_ID")
    
    @staticmethod
    def get_accounting_sheet_id():
        """Obtiene ID de la hoja de cálculo de contabilidad."""
        if IS_PRODUCTION:
            return st.secrets["google"]["accounting_sheet_id"]
        else:
            return os.getenv("ACCOUNTING_SHEET_ID")
    
    @staticmethod
    def get_session_secret():
        """Obtiene clave secreta para sesiones."""
        if IS_PRODUCTION:
            return st.secrets["app"]["session_secret"]
        else:
            return os.getenv("SESSION_SECRET", "your-default-secret-key")
    
    @staticmethod
    def is_debug_mode():
        """Verifica si está en modo debug."""
        if IS_PRODUCTION:
            return False  # Nunca debug en producción
        else:
            return os.getenv("DEBUG", "False") == "True"

# Cargar variables de entorno solo en desarrollo
if IS_DEVELOPMENT:
    load_dotenv()

# Función helper para logging
def log_environment():
    """Registra información del entorno actual."""
    env_type = "PRODUCTION (Streamlit Cloud)" if IS_PRODUCTION else "DEVELOPMENT (Local)"
    print(f"🌍 Environment: {env_type}")
    
    if IS_PRODUCTION:
        print("📊 Using: Supabase PostgreSQL + Streamlit Secrets")
    else:
        print("💻 Using: Local SQLite + .env file")

# Exportar configuración actual
DATABASE_URL = ProductionConfig.get_database_url()
CALENDAR_ID = ProductionConfig.get_calendar_id()
ACCOUNTING_SHEET_ID = ProductionConfig.get_accounting_sheet_id()
SESSION_SECRET = ProductionConfig.get_session_secret()
DEBUG = ProductionConfig.is_debug_mode()

# Solo para debugging en desarrollo
if IS_DEVELOPMENT and DEBUG:
    log_environment()