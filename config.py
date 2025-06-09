# config.py
import os
import datetime as dt
from pathlib import Path

# 🆕 NUEVO: Importar configuración de producción
from config_production import (
    DATABASE_URL, CALENDAR_ID, ACCOUNTING_SHEET_ID, 
    SESSION_SECRET, DEBUG, IS_PRODUCTION, IS_DEVELOPMENT,
    ProductionConfig
)

# Directorios base del proyecto
BASE_DIR = Path(__file__).parent
DATA_DIR = os.path.join(BASE_DIR, "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
STYLES_DIR = os.path.join(BASE_DIR, "styles")
PROFILE_PHOTOS_DIR = os.path.join(ASSETS_DIR, "profile_photos")

# Crear directorios solo en desarrollo (en producción no los necesitamos)
if IS_DEVELOPMENT:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(STYLES_DIR, exist_ok=True)
    os.makedirs(PROFILE_PHOTOS_DIR, exist_ok=True)

# Rutas de archivos importantes
if IS_DEVELOPMENT:
    # Desarrollo: usar rutas locales
    DATABASE_PATH = os.path.join(DATA_DIR, "ballers_app.db")
    DEFAULT_PROFILE_PHOTO = os.path.join(ASSETS_DIR, "default_profile.png")
    CSS_FILE = os.path.join(STYLES_DIR, "style.css")
else:
    # Producción: base de datos es PostgreSQL, archivos estáticos diferentes
    DATABASE_PATH = None  # No aplica, usamos DATABASE_URL
    DEFAULT_PROFILE_PHOTO = "assets/profile_photos/default_profile.png"
    CSS_FILE = "styles/style.css"

# Configuración de la aplicación Streamlit
APP_NAME = "Ballers App"
APP_ICON = "assets/ballers/favicon.ico"

# 🔧 ACTUALIZADO: Usar configuración según entorno
# Las variables importantes ahora vienen de config_production.py
# CALENDAR_ID, ACCOUNTING_SHEET_ID, SESSION_SECRET, DEBUG ya están importadas

# Configuración de la aplicación
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Lista de tipos de archivos permitidos para fotos de perfil
ALLOWED_PHOTO_EXTENSIONS = ["jpg", "jpeg", "png"]
MAX_PHOTO_SIZE_MB = 2

# Constantes de la aplicación
SESSION_DURATION_DEFAULT = 60  # minutos

# Colores para las sesiones (código Google Calendar + color HEX para la UI)
CALENDAR_COLORS = {
    "scheduled": {"google": "9",  "hex": "#1E88E5"},  # azul
    "completed": {"google": "2",  "hex": "#4CAF50"},  # verde
    "canceled":  {"google": "11", "hex": "#F44336"},  # rojo
}

# Horarios para formularios de la app (estrictos)
WORK_HOURS_STRICT = {
    "start": dt.time(8, 0),
    "end": dt.time(18, 0)
}

# Horarios para imports de Calendar (flexibles)
WORK_HOURS_FLEXIBLE = {
    "start": dt.time(6, 0),
    "end": dt.time(22, 0)
}

SESSION_DURATION = {
    "min_minutes": 60,
    "max_minutes": 120,  # 2 horas para formularios
    "max_minutes_import": 180  # 3 horas para imports (antes de rechazar)
}

# 🆕 NUEVO: Función para logging del entorno
def log_config_info():
    """Muestra información de configuración al inicio."""
    env_name = "PRODUCTION" if IS_PRODUCTION else "DEVELOPMENT"
    db_type = "PostgreSQL (Supabase)" if IS_PRODUCTION else "SQLite (Local)"
    
    print(f"🚀 Ballers App starting in {env_name} mode")
    print(f"💾 Database: {db_type}")
    print(f"📅 Calendar ID: {CALENDAR_ID}")
    print(f"🔐 Debug mode: {DEBUG}")

