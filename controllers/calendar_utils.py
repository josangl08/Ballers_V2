# controllers/calendar_utils.py
"""
Utilidades compartidas para manejo de calendario y sesiones.
Funciones puras sin dependencias externas.
"""
import hashlib
import datetime as dt
import re
import logging
from zoneinfo import ZoneInfo
from typing import Optional
from models import Session, SessionStatus
from common.utils import format_time_local, normalize_datetime_for_hash
from config import TIMEZONE
from config import TIMEZONE_NAME
from config import CALENDAR_COLORS

LOCAL_TZ = TIMEZONE
logger = logging.getLogger(__name__)

def calculate_session_hash(session: Session) -> str:
    """Calcula hash MD5 basado en datos importantes de la sesión CON FECHAS NORMALIZADAS."""
    try:
        # Normalizar fechas
        start_normalized = normalize_datetime_for_hash(session.start_time)
        end_normalized = normalize_datetime_for_hash(session.end_time)
        
        data = "|".join([
            str(session.coach_id),
            str(session.player_id), 
            start_normalized,
            end_normalized,
            session.status.value,
            session.notes or ""
        ])
        
        hash_result = hashlib.md5(data.encode('utf-8')).hexdigest()
        logger.debug(f"🔧 Session hash data: '{data}' → {hash_result[:8]}...")
        return hash_result
        
    except Exception as e:
        logger.warning(f"⚠️ Error calculando hash sesión #{session.id}: {e}")
        return ""


def calculate_event_hash(event_data: dict) -> str:
    """Calcula hash MD5 basado en datos importantes del evento CON FECHAS NORMALIZADAS."""
    try:
        def _to_dt_local(iso: str) -> dt.datetime:
            return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        
        # Obtener fechas del evento y normalizarlas
        start_dt = _to_dt_local(event_data["start"]["dateTime"])
        end_dt = _to_dt_local(event_data["end"]["dateTime"])
        
        start_normalized = normalize_datetime_for_hash(start_dt)
        end_normalized = normalize_datetime_for_hash(end_dt)
        
        # Importar aquí para evitar circular import
        status = status_from_color(event_data.get("colorId", "9"))
        
        props = event_data.get("extendedProperties", {}).get("private", {})
        coach_id = props.get("coach_id", "")
        player_id = props.get("player_id", "")
        
        data = "|".join([
            str(coach_id),
            str(player_id),
            start_normalized,
            end_normalized,
            status.value,
            event_data.get("description", "") or ""
        ])
        
        hash_result = hashlib.md5(data.encode('utf-8')).hexdigest()
        logger.debug(f"🔧 Event hash data: '{data}' → {hash_result[:8]}...")
        return hash_result
        
    except Exception as e:
        logger.warning(f"⚠️ Error calculando hash evento: {e}")
        return ""


def build_calendar_event_body(session: Session) -> dict:
    """
    Devuelve el diccionario body que Calendar API espera.
    🔧 FIX: Maneja correctamente datetime naive de BD.
    """
    
    COLOR = {k: v["google"] for k, v in CALENDAR_COLORS.items()}
    
    # 🔧 FIX: Si los datetime de BD son naive, asumir que están en TIMEZONE local
    if session.start_time.tzinfo is None:
        # Datetime naive - asumir que está en timezone local
        start_local = session.start_time
        end_local = session.end_time
    else:
        # Datetime con timezone - convertir a local y quitar tzinfo
        start_local = session.start_time.astimezone(LOCAL_TZ).replace(tzinfo=None)
        end_local = session.end_time.astimezone(LOCAL_TZ).replace(tzinfo=None)
    
    # Convertir a ISO string SIN timezone info
    start = start_local.isoformat()  # "2025-06-11T08:00:00"
    end = end_local.isoformat()      # "2025-06-11T09:00:00"
    
    return {
        "summary": (
            f"Session: {session.coach.user.name} × {session.player.user.name} "
            f"#C{session.coach_id} #P{session.player_id}"
        ),
        "description": session.notes or "",
        "start": {"dateTime": start, "timeZone": TIMEZONE_NAME},  # timezone solo aquí
        "end":   {"dateTime": end,   "timeZone": TIMEZONE_NAME},    # timezone solo aquí
        "colorId": COLOR[session.status.value],
        "extendedProperties": {
            "private": {
                "session_id": str(session.id),
                "coach_id":   str(session.coach_id),
                "player_id":  str(session.player_id),
            }
        },
    }


def update_session_tracking(session: Session):
    """Actualiza campos de tracking después de cambios."""
    try:
        session.sync_hash = calculate_session_hash(session)
        session.updated_at = dt.datetime.now(dt.timezone.utc)
        session.last_sync_at = dt.datetime.now(dt.timezone.utc)
        session.is_dirty = False
        session.version = (session.version or 0) + 1
        
        logger.debug(f"📝 Tracking actualizado: Sesión #{session.id} v{session.version}")
    except Exception as e:
        logger.warning(f"⚠️ Error actualizando tracking sesión #{session.id}: {e}")


def session_has_real_changes(session: Session) -> bool:
    """Verifica si una sesión tiene cambios REALES que justifiquen update"""
    # 1. Si está marcada como dirty → hay cambios
    if hasattr(session, 'is_dirty') and session.is_dirty:
        logger.debug(f"🔄 Sesión #{session.id} marcada como dirty")
        return True
    
    # 2. Si no tiene hash → primera vez
    if not session.sync_hash:
        logger.debug(f"🔄 Sesión #{session.id} sin hash - primera sincronización")
        return True
    
    # 3. Comparar hash actual vs. guardado
    current_hash = calculate_session_hash(session)
    
    if session.sync_hash != current_hash:
        logger.debug(f"🔄 Sesión #{session.id} hash cambió: {session.sync_hash[:8]}... → {current_hash[:8]}...")
        return True
    
    # 4. Sin cambios reales
    logger.debug(f"✅ Sesión #{session.id} - sin cambios reales")
    return False


def session_needs_update(session: Session) -> bool:
    """Versión simple - Solo actualizar si está dirty o no tiene hash"""
    # 1. Si está dirty → actualizar
    if hasattr(session, 'is_dirty') and session.is_dirty:
        return True
    
    # 2. Si no tiene hash → actualizar
    if not session.sync_hash:
        return True
        
    # 3. Verificar cambios en hash
    current_hash = calculate_session_hash(session)
    has_changes = session.sync_hash != current_hash
    
    if has_changes:
        logger.debug(f"🔄 Sesión #{session.id} - cambios detectados en hash")
    
    return has_changes


# Utilidades de parsing y mapeo


def safe_int(value):
    """Convierte valor a int de forma segura."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_text(text: str) -> str:
    """Pasa a minúsculas, quita tildes y unifica espacios."""
    from unidecode import unidecode
    return re.sub(r"\s+", " ", unidecode(text or "").strip().lower())


def extract_id_from_text(text: str, pattern: str):
    """Busca con regex y devuelve el grupo 1 como int, o None."""
    m = re.search(pattern, text, flags=re.I)
    return safe_int(m.group(1)) if m else None


def find_unique_user(model_class, name_norm: str):
    """
    Trae todos los registros del modelo (Coach o Player),
    normaliza user.name y devuelve el único que coincide con name_norm.
    Si hay 0 o >1, devuelve None.
    """
    from controllers.db import get_db_session
    from models import User
    
    db = get_db_session()
    try:
        rows = (
            db.query(model_class)
            .join(User)
            .filter(User.is_active)
            .all()
        )
        matches = [r for r in rows if normalize_text(r.user.name) == name_norm]
        return matches[0] if len(matches) == 1 else None
    finally:
        db.close()

def status_from_color(color: str) -> SessionStatus:
    """
    Dado un colorId de Google Calendar, devuelve el estado correspondiente.
    • Reds → CANCELED
    • Greens → COMPLETED  
    • El resto → SCHEDULED
    """
    cid = str(color)

    # Todos los rojos → canceled
    red_ids = {"11", "6"}
    if cid in red_ids:
        return SessionStatus.CANCELED

    # Todos los verdes → completed
    green_ids = {"2", "10"}
    if cid in green_ids:
        return SessionStatus.COMPLETED

    # El resto → scheduled
    return SessionStatus.SCHEDULED        