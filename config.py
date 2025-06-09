# config.py
"""
Configuración unificada para Ballers App.
Prioriza producción (Streamlit Cloud + Supabase) con fallback a desarrollo local.
"""
import os
import datetime as dt
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

# Detectar entorno
def is_production():
    """Detecta si estamos en producción (Streamlit Cloud)."""
    return (
        "STREAMLIT_SHARING" in os.environ or 
        "STREAMLIT_CLOUD" in os.environ or
        os.getenv("STREAMLIT_SERVER_PORT") is not None
    )

IS_PRODUCTION = is_production()
IS_DEVELOPMENT = not IS_PRODUCTION

# Cargar .env solo en desarrollo
if IS_DEVELOPMENT:
    load_dotenv()

# =============================================================================
# CONFIGURACIÓN DE BASE DE DATOS
# =============================================================================

def get_database_url():
    """Obtiene URL de base de datos (PostgreSQL en producción, SQLite en desarrollo)."""
    if IS_PRODUCTION:
        try:
            # Producción: usar DATABASE_URL directo de secrets
            return st.secrets["DATABASE_URL"]
        except:
            # Fallback: construir desde secrets de database
            return (
                f"postgresql://{st.secrets['database']['username']}:"
                f"{st.secrets['database']['password']}@"
                f"{st.secrets['database']['host']}:"
                f"{st.secrets['database']['port']}/"
                f"{st.secrets['database']['database']}"
            )
    else:
        # Desarrollo: SQLite local
        return f"sqlite:///{os.getenv('DATABASE_PATH', 'data/ballers_app.db')}"

DATABASE_URL = get_database_url()

# =============================================================================
# CONFIGURACIÓN DE GOOGLE APIS
# =============================================================================

def get_calendar_id():
    """Obtiene ID del calendario de Google."""
    if IS_PRODUCTION:
        try:
            return st.secrets["google"]["calendar_id"]
        except:
            return "info@ballersbangkok.com"  # Default de producción
    else:
        return os.getenv("CALENDAR_ID", "josangl08@usal.es")

def get_accounting_sheet_id():
    """Obtiene ID de la hoja de cálculo de contabilidad."""
    if IS_PRODUCTION:
        try:
            return st.secrets["google"]["accounting_sheet_id"]
        except:
            return "1Lf1lpplLOrewG4V-8949Ny9PLg6nX5n9_GgIWtQWqQY"  # Default de producción
    else:
        return os.getenv("ACCOUNTING_SHEET_ID", "1ZH53dleTQRzt6Tvhobi7cLwoVDaDfuOtLe3UdvtRVR0")

def get_google_credentials():
    """Obtiene credenciales de Google (secrets en producción, archivo en desarrollo)."""
    if IS_PRODUCTION:
        try:
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
        except Exception as e:
            print(f"⚠️ Error leyendo credenciales de Google desde secrets: {e}")
            return None
    else:
        # Desarrollo: usar archivo local
        return None

# Variables de configuración
CALENDAR_ID = get_calendar_id()
ACCOUNTING_SHEET_ID = get_accounting_sheet_id()
GOOGLE_CREDENTIALS = get_google_credentials()

# =============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# =============================================================================

def get_session_secret():
    """Obtiene clave secreta para sesiones."""
    if IS_PRODUCTION:
        try:
            return st.secrets["app"]["session_secret"]
        except:
            return "ballers-app-production-2025-secure-key-Q4FAATxa4mw9sZk"
    else:
        return os.getenv("SESSION_SECRET", "your-default-secret-key")

def is_debug_mode():
    """Verifica si está en modo debug."""
    if IS_PRODUCTION:
        return False  # Nunca debug en producción
    else:
        return os.getenv("DEBUG", "False") == "True"

SESSION_SECRET = get_session_secret()
DEBUG = is_debug_mode()

# =============================================================================
# DIRECTORIOS Y RUTAS
# =============================================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = os.path.join(BASE_DIR, "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
STYLES_DIR = os.path.join(BASE_DIR, "styles")
PROFILE_PHOTOS_DIR = os.path.join(ASSETS_DIR, "profile_photos")

# Crear directorios solo en desarrollo
if IS_DEVELOPMENT:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(STYLES_DIR, exist_ok=True)
    os.makedirs(PROFILE_PHOTOS_DIR, exist_ok=True)

# Rutas específicas según entorno
if IS_DEVELOPMENT:
    DATABASE_PATH = os.path.join(DATA_DIR, "ballers_app.db")
    GOOGLE_SA_PATH = os.getenv("GOOGLE_SA_PATH", "data/google_service_account.json")
    DEFAULT_PROFILE_PHOTO = os.path.join(ASSETS_DIR, "default_profile.png")
    CSS_FILE = os.path.join(STYLES_DIR, "style.css")
else:
    DATABASE_PATH = None  # Usamos DATABASE_URL
    GOOGLE_SA_PATH = None  # Usamos GOOGLE_CREDENTIALS
    DEFAULT_PROFILE_PHOTO = "assets/profile_photos/default_profile.png"
    CSS_FILE = "styles/style.css"

# =============================================================================
# CONFIGURACIÓN DE STREAMLIT
# =============================================================================

APP_NAME = "Ballers App"
APP_ICON = "assets/ballers/favicon.ico"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# =============================================================================
# CONFIGURACIÓN DE NEGOCIO
# =============================================================================

# Archivos permitidos
ALLOWED_PHOTO_EXTENSIONS = ["jpg", "jpeg", "png"]
MAX_PHOTO_SIZE_MB = 2

# Constantes de sesiones
SESSION_DURATION_DEFAULT = 60  # minutos

# Colores para Calendar
CALENDAR_COLORS = {
    "scheduled": {"google": "9",  "hex": "#1E88E5"},  # azul
    "completed": {"google": "2",  "hex": "#4CAF50"},  # verde
    "canceled":  {"google": "11", "hex": "#F44336"},  # rojo
}

# Horarios de trabajo
WORK_HOURS_STRICT = {
    "start": dt.time(8, 0),
    "end": dt.time(18, 0)
}

WORK_HOURS_FLEXIBLE = {
    "start": dt.time(6, 0),
    "end": dt.time(22, 0)
}

SESSION_DURATION = {
    "min_minutes": 60,
    "max_minutes": 120,  # formularios
    "max_minutes_import": 180  # imports
}

# =============================================================================
# FUNCIÓN DE LOGGING
# =============================================================================

def log_config_info():
    """Muestra información de configuración al inicio."""
    env_name = "PRODUCTION" if IS_PRODUCTION else "DEVELOPMENT"
    db_type = "PostgreSQL (Supabase)" if IS_PRODUCTION else "SQLite (Local)"
    
    print(f"🚀 Ballers App starting in {env_name} mode")
    print(f"💾 Database: {db_type}")
    print(f"📅 Calendar ID: {CALENDAR_ID}")
    print(f"📊 Sheet ID: {ACCOUNTING_SHEET_ID}")
    print(f"🔐 Debug mode: {DEBUG}")
    
    if IS_PRODUCTION:
        print("✅ Using Streamlit secrets for configuration")
    else:
        print("💻 Using .env file for configuration")