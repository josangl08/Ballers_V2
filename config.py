# config.py
"""
Configuración unificada para Ballers App - SIMPLIFICADA
"""
import os
import datetime as dt
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)
load_dotenv()

# =============================================================================
# DETECCIÓN DE ENTORNO SIMPLIFICADA
# =============================================================================

# En Streamlit Cloud, definir ENVIRONMENT=production en secrets

def detect_production_environment():
    """Detecta si estamos en producción usando múltiples métodos"""
    
    # Método 1: Variable ENVIRONMENT en secrets/env
    env_var = os.getenv("ENVIRONMENT", "").lower()
    if env_var:
        return env_var.lower() == "production"   # Devuelve True o False y se sale
    
    # Método 2: Detección por hostname (Streamlit Cloud)
    import socket
    hostname = socket.gethostname().lower()
    if "streamlit" in hostname or "cloud" in hostname:
        return True
    
    # Método 3: Detección por secrets de Streamlit
    if hasattr(st, 'secrets'):
        try:
            # Si hay secrets configurados, probablemente es producción
            if 'google' in st.secrets and 'DATABASE_URL' in st.secrets:
                return True
        except:
            pass
    
    # Método 4: Variable de entorno de Streamlit Cloud
    if os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("STREAMLIT_CLOUD"):
        return True
    
    return False

# Usar detección mejorada
IS_PRODUCTION = detect_production_environment()
IS_DEVELOPMENT = not IS_PRODUCTION

print(f"🌍 Entorno detectado: {'PRODUCTION' if IS_PRODUCTION else 'DEVELOPMENT'}")

# =============================================================================
# CONFIGURACIÓN DE BASE DE DATOS
# =============================================================================

def get_database_url():
    """Obtiene URL de base de datos."""
    if IS_PRODUCTION:
        # En producción, buscar en secrets o env
        if hasattr(st, 'secrets') and 'DATABASE_URL' in st.secrets:
            return st.secrets["DATABASE_URL"]
        return os.getenv("DATABASE_URL", "")
    else:
        # En desarrollo, usar SQLite
        db_path = os.getenv('DATABASE_PATH', 'data/ballers_app.db')
        return f"sqlite:///{db_path}"

DATABASE_URL = get_database_url()
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no configurado")

# =============================================================================
# CONFIGURACIÓN DE GOOGLE APIS
# =============================================================================

def get_google_config():
    """Obtiene configuración de Google unificada."""
    config = {}
    
    if IS_PRODUCTION:
        # Producción: usar secrets de Streamlit
        if hasattr(st, 'secrets') and 'google' in st.secrets:
            config['calendar_id'] = st.secrets.google.get('calendar_id', 'info@ballersbangkok.com')
            config['sheet_id'] = st.secrets.google.get('accounting_sheet_id', '1Lf1lpplLOrewG4V-8949Ny9PLg6nX5n9_GgIWtQWqQY')
            
            # Construir credenciales desde secrets
            config['credentials'] = {
                "type": st.secrets.google.type,
                "project_id": st.secrets.google.project_id,
                "private_key_id": st.secrets.google.private_key_id,
                "private_key": st.secrets.google.private_key.replace('\\n', '\n'),  # Fix newlines
                "client_email": st.secrets.google.client_email,
                "client_id": st.secrets.google.client_id,
                "auth_uri": st.secrets.google.auth_uri,
                "token_uri": st.secrets.google.token_uri,
                "auth_provider_x509_cert_url": st.secrets.google.auth_provider_x509_cert_url,
                "client_x509_cert_url": st.secrets.google.client_x509_cert_url,
                "universe_domain": st.secrets.google.get("universe_domain", "googleapis.com")
            }
        else:
            raise ValueError("Secrets de Google no encontrados en producción")
    else:
        # Desarrollo: usar .env
        config['calendar_id'] = os.getenv('CALENDAR_ID', 'josangl08@usal.es')
        config['sheet_id'] = os.getenv('ACCOUNTING_SHEET_ID', '1ZH53dleTQRzt6Tvhobi7cLwoVDaDfuOtLe3UdvtRVR0')
        config['credentials'] = None  # Usar archivo local
        config['service_account_path'] = os.getenv('GOOGLE_SA_PATH', 'data/google_service_account.json')
    
    return config

# Obtener configuración
try:
    google_config = get_google_config()
    CALENDAR_ID = google_config['calendar_id']
    ACCOUNTING_SHEET_ID = google_config['sheet_id']
    GOOGLE_CREDENTIALS = google_config.get('credentials')
    GOOGLE_SA_PATH = google_config.get('service_account_path')
    
    print(f"✅ Google Config: Calendar={CALENDAR_ID[:20]}..., Sheet={ACCOUNTING_SHEET_ID[:20]}...")
except Exception as e:
    print(f"❌ Error configurando Google APIs: {e}")
    # Valores por defecto
    CALENDAR_ID = "josangl08@usal.es"
    ACCOUNTING_SHEET_ID = "1ZH53dleTQRzt6Tvhobi7cLwoVDaDfuOtLe3UdvtRVR0"
    GOOGLE_CREDENTIALS = None
    GOOGLE_SA_PATH = "data/google_service_account.json"

# =============================================================================
# RESTO DE CONFIGURACIONES (sin cambios)
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
    DEFAULT_PROFILE_PHOTO = os.path.join(ASSETS_DIR, "default_profile.png")
    CSS_FILE = os.path.join(STYLES_DIR, "style.css")
else:
    DATABASE_PATH = None
    DEFAULT_PROFILE_PHOTO = "assets/profile_photos/default_profile.png"
    CSS_FILE = "styles/style.css"

# Configuración de la aplicación
APP_NAME = "Ballers App"
APP_ICON = "assets/ballers/favicon.ico"
SESSION_SECRET = os.getenv("SESSION_SECRET", "ballers-app-default-secret-key")
DEBUG = os.getenv("DEBUG", "False") == "True"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Archivos permitidos
ALLOWED_PHOTO_EXTENSIONS = ["jpg", "jpeg", "png"]
MAX_PHOTO_SIZE_MB = 2

# Constantes de sesiones
SESSION_DURATION_DEFAULT = 60

# Colores para Calendar
CALENDAR_COLORS = {
    "scheduled": {"google": "9",  "hex": "#1E88E5"},
    "completed": {"google": "2",  "hex": "#4CAF50"},
    "canceled":  {"google": "11", "hex": "#F44336"},
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
    "max_minutes": 120,
    "max_minutes_import": 180
}



# Zona horaria de la aplicación
if IS_PRODUCTION:
    # Producción: Tailandia
    TIMEZONE = ZoneInfo("Asia/Bangkok")
    TIMEZONE_NAME = "Asia/Bangkok"
    UTC_OFFSET_HOURS = 7
    print("🇹🇭 Configurando timezone para Tailandia (Asia/Bangkok)")
else:
    # Desarrollo: España
    TIMEZONE = ZoneInfo("Europe/Madrid")
    TIMEZONE_NAME = "Europe/Madrid"
    UTC_OFFSET_HOURS = 2  # Aproximado, varía con DST
    print("🇪🇸 Configurando timezone para España (Europe/Madrid)")

print(f"🌍 Timezone activo: {TIMEZONE_NAME} (UTC+{UTC_OFFSET_HOURS})")

# Verificar que funciona correctamente
current_time = dt.datetime.now(TIMEZONE)
print(f"⏰ Hora actual en {TIMEZONE_NAME}: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")


def log_config_info():
    """Muestra información de configuración al inicio."""
    env_name = "PRODUCTION" if IS_PRODUCTION else "DEVELOPMENT"
    db_type = "PostgreSQL (Supabase)" if IS_PRODUCTION else "SQLite (Local)"
    
    logger.info("="*60)
    logger.info(f"🚀 Ballers App - {env_name}")
    logger.info(f"💾 Database: {db_type}")
    logger.info(f"🌍 Timezone: {TIMEZONE_NAME} (UTC+{UTC_OFFSET_HOURS})")
    logger.info(f"📅 Calendar: {CALENDAR_ID}")
    logger.info(f"📊 Sheet: {ACCOUNTING_SHEET_ID}")
    logger.info(f"🔐 Debug: {DEBUG}")
    logger.info(f"⏰ Hora actual: {dt.datetime.now(TIMEZONE).strftime('%H:%M:%S %Z')}")
    logger.info("="*60)