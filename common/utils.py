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
    Convierte datetime UTC a hora local Madrid para logging legible.
    
    Args:
        dt_obj: Datetime object (puede ser None)
        
    Returns:
        str: Hora formateada en formato HH:MM o "None"
    """
    if dt_obj is None:
        return "None"
        
    # Asegurar que tiene timezone info
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    
    # Convertir a hora local
    try:
        local_time = dt_obj.astimezone(TIMEZONE)
        return local_time.strftime('%H:%M')
    except:
        # Fallback si no funciona timezone
        return dt_obj.strftime('%H:%M')


def normalize_datetime_for_hash(dt_obj) -> str:
    """
    Normaliza datetime para hash: convierte a UTC y quita timezone info.
    
    Args:
        dt_obj: Datetime object o string ISO
        
    Returns:
        str: Datetime normalizado en formato ISO
    """
    if dt_obj is None:
        return ""
    
    # Si es string, convertir a datetime primero
    if isinstance(dt_obj, str):
        try:
            dt_obj = dt.datetime.fromisoformat(dt_obj.replace("Z", "+00:00"))
        except:
            return dt_obj  # Si falla, devolver como está
    
    # Manejar datetime naive (asumir timezone local Madrid)
    if dt_obj.tzinfo is None:
        try:
            dt_obj = dt_obj.replace(tzinfo=TIMEZONE)
        except:
            # Fallback: usar offset configurado
            dt_obj = dt_obj.replace(tzinfo=dt.timezone(dt.timedelta(hours=UTC_OFFSET_HOURS)))
    
    # Convertir a UTC y quitar timezone info para consistencia
    utc_naive = dt_obj.astimezone(dt.timezone.utc).replace(tzinfo=None)
    
    # Devolver formato ISO sin microsegundos
    return utc_naive.replace(microsecond=0).isoformat()

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