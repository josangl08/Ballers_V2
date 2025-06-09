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

# =============================================================================
# DETECCIÓN DE ENTORNO CORREGIDA
# =============================================================================

def is_production():
    """
    Detecta si estamos en producción de forma MÁS ESTRICTA.
    Solo considera producción si hay evidencia clara de Streamlit Cloud.
    """
    # Método 1: Variables de entorno específicas de Streamlit Cloud
    streamlit_cloud_vars = [
        "STREAMLIT_SHARING", 
        "STREAMLIT_CLOUD"
    ]
    
    if any(var in os.environ for var in streamlit_cloud_vars):
        print(f"🌍 Producción detectada por variable: {[var for var in streamlit_cloud_vars if var in os.environ]}")
        return True
    
    # Método 2: STREAMLIT_SERVER_PORT solo si no hay archivo .env
    if "STREAMLIT_SERVER_PORT" in os.environ and not os.path.exists(".env"):
        print("🌍 Producción detectada por STREAMLIT_SERVER_PORT (sin .env local)")
        return True
    
    # Método 3: Verificar si hay secrets de Streamlit disponibles (MÁS ESTRICTO)
    try:
        if hasattr(st, 'secrets'):
            # Verificar que tenga secrets específicos de producción
            if (hasattr(st.secrets, 'database') and 
                hasattr(st.secrets, 'google') and
                not os.path.exists(".env")):  # Y no hay .env local
                print("🌍 Producción detectada por secrets (sin .env local)")
                return True
    except:
        pass
    
    # Por defecto: desarrollo
    print("💻 Desarrollo detectado")
    return False

IS_PRODUCTION = is_production()
IS_DEVELOPMENT = not IS_PRODUCTION

# Cargar .env solo en desarrollo
if IS_DEVELOPMENT:
    load_dotenv()
    print("📁 Archivo .env cargado para desarrollo")

# =============================================================================
# CONFIGURACIÓN DE BASE DE DATOS
# =============================================================================

def get_database_url():
    """Obtiene URL de base de datos (PostgreSQL en producción, SQLite en desarrollo)."""
    if IS_PRODUCTION:
        try:
            # Método 1: DATABASE_URL directo de secrets
            if hasattr(st, 'secrets') and hasattr(st.secrets, 'DATABASE_URL'):
                return st.secrets["DATABASE_URL"]
        except:
            pass
        
        try:
            # Método 2: Construir desde secrets de database
            if hasattr(st, 'secrets') and hasattr(st.secrets, 'database'):
                return (
                    f"postgresql://{st.secrets['database']['username']}:"
                    f"{st.secrets['database']['password']}@"
                    f"{st.secrets['database']['host']}:"
                    f"{st.secrets['database']['port']}/"
                    f"{st.secrets['database']['database']}"
                )
        except:
            pass
        
        # Método 3: Variable de entorno DATABASE_URL
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url
        
        # Fallback si falla todo
        raise ValueError("No se pudo obtener DATABASE_URL en producción")
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
            if hasattr(st, 'secrets') and hasattr(st.secrets, 'google'):
                return st.secrets["google"]["calendar_id"]
        except:
            pass
        # Fallback producción
        return "info@ballersbangkok.com"
    else:
        return os.getenv("CALENDAR_ID", "josangl08@usal.es")

def get_accounting_sheet_id():
    """Obtiene ID de la hoja de cálculo de contabilidad."""
    if IS_PRODUCTION:
        try:
            if hasattr(st, 'secrets') and hasattr(st.secrets, 'google'):
                return st.secrets["google"]["accounting_sheet_id"]
        except:
            pass
        # Fallback producción
        return "1Lf1lpplLOrewG4V-8949Ny9PLg6nX5n9_GgIWtQWqQY"
    else:
        return os.getenv("ACCOUNTING_SHEET_ID", "1ZH53dleTQRzt6Tvhobi7cLwoVDaDfuOtLe3UdvtRVR0")

def get_google_credentials():
    """Obtiene credenciales de Google (secrets en producción, archivo en desarrollo)."""
    if IS_PRODUCTION:
        try:
            if hasattr(st, 'secrets') and hasattr(st.secrets, 'google'):
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

print(f"🔧 CONFIG DEBUG - CALENDAR_ID: {CALENDAR_ID}")  # Para debugging

# =============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# =============================================================================

def get_session_secret():
    """Obtiene clave secreta para sesiones."""
    if IS_PRODUCTION:
        try:
            if hasattr(st, 'secrets') and hasattr(st.secrets, 'app'):
                return st.secrets["app"]["session_secret"]
        except:
            pass
        # Fallback producción
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
# FUNCIÓN DE LOGGING (NO SE EJECUTA AUTOMÁTICAMENTE)
# =============================================================================

def log_config_info():
    """
    Muestra información de configuración al inicio.
    IMPORTANTE: Esta función NO se ejecuta automáticamente al importar.
    Debe ser llamada explícitamente desde main.py.
    """
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