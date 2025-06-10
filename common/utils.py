"""
Utilidades compartidas para toda la aplicación Ballers.
Funciones reutilizables que no dependen de UI específica.
"""
import hashlib
import datetime as dt
from typing import Optional
from config import TIMEZONE, UTC_OFFSET_HOURS

def hash_password(password: str) -> str:
    """
    Convierte una contraseña en un hash SHA-256.
    
    Args:
        password: Contraseña en texto plano
        
    Returns:
        str: Hash SHA-256 de la contraseña
    """
    return hashlib.sha256(password.encode()).hexdigest()


def format_time_local(dt_obj: Optional[dt.datetime]) -> str:
    """
    Devuelve la hora local (según TIMEZONE) en formato 'HH:MM'.
    Acepta datetime naive o con tzinfo; None → "None".
    """
    if dt_obj is None:
        return "None"
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    return dt_obj.astimezone(TIMEZONE).strftime("%H:%M")

def to_calendar_str(dt_obj: dt.datetime) -> str:
    """
    Convierte cualquier datetime a string 'YYYY-MM-DDTHH:MM:SS'
    en la zona activa (TIMEZONE) **sin** offset, para FullCalendar.
    """
    if dt_obj.tzinfo:
        dt_obj = dt_obj.astimezone(TIMEZONE)
    else:
        dt_obj = dt_obj.replace(tzinfo=TIMEZONE)
    return dt_obj.strftime("%Y-%m-%dT%H:%M:%S")


def normalize_datetime_for_hash(dt_obj) -> str:
    """
    Normaliza un datetime para hashing:
    1) lo interpreta en TIMEZONE si es naive,
    2) lo convierte a UTC,
    3) elimina tzinfo y microsegundos.
    """
    if dt_obj is None:
        return ""
    if isinstance(dt_obj, str):
        dt_obj = dt.datetime.fromisoformat(dt_obj.replace("Z", "+00:00"))
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=TIMEZONE)
    utc_naive = dt_obj.astimezone(dt.timezone.utc).replace(tzinfo=None, microsecond=0)
    return utc_naive.isoformat()

def app_health_check() -> dict:
    """
    Verifica el estado de salud de la aplicación.
    Útil para deployment y debugging.
    """
    import os
    
    health = {
        "status": "healthy",
        "timestamp": dt.datetime.now().isoformat(),
        "checks": {}
    }
    
    # Verificar archivos críticos
    critical_files = [
        "data/ballers_app.db",
        "data/google_service_account.json",
        ".env"
    ]
    
    for file_path in critical_files:
        exists = os.path.exists(file_path)
        health["checks"][file_path] = "✅" if exists else "❌"
        if not exists:
            health["status"] = "warning"
    
    # Verificar variables de entorno
    required_env_vars = [
        "CALENDAR_ID",
        "ACCOUNTING_SHEET_ID",
        "GOOGLE_SA_PATH"
    ]
    
    for var in required_env_vars:
        value = os.getenv(var)
        health["checks"][f"ENV_{var}"] = "✅" if value else "❌"
        if not value:
            health["status"] = "warning"
    
    # Verificar conexión a base de datos
    try:
        from controllers.db import get_db_session
        db = get_db_session()
        db.close()
        health["checks"]["database_connection"] = "✅"
    except Exception as e:
        health["checks"]["database_connection"] = f"❌ {str(e)}"
        health["status"] = "error"
    
    return health