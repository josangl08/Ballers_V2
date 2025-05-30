import streamlit as st
import datetime as dt
import os
import re 
import logging
import time
import hashlib
from googleapiclient.errors import HttpError
from sqlalchemy import func
from sqlalchemy.orm import object_session, Session as AlchSession
from .google_client import calendar
from googleapiclient.errors import HttpError
from models import Session, SessionStatus, Coach, Player, User        
from controllers.db import get_db_session
from unidecode import unidecode
from config import CALENDAR_COLORS
COLOR = {k: v["google"] for k, v in CALENDAR_COLORS.items()} 
CAL_ID = os.getenv("CALENDAR_ID")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Handler para mostrar en streamlit si no existe
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def _db():
    return get_db_session()

def _service():
    return calendar()

def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
    
d_safe_int = lambda x: int(x) if x and str(x).isdigit() else None

def _normalize(text: str) -> str:
    """Pasa a minúsculas, quita tildes y unifica espacios."""
    return re.sub(r"\s+", " ", unidecode(text or "").strip().lower())

def _extract_id(text: str, pattern: str):
    """Busca con regex y devuelve el grupo 1 como int, o None."""
    m = re.search(pattern, text, flags=re.I)
    return _safe_int(m.group(1)) if m else None

def _find_unique(model, name_norm: str):
    """
    Trae todos los registros del modelo (Coach o Player),
    normaliza user.name y devuelve el único que coincide con name_norm.
    Si hay 0 o >1, devuelve None.
    """
    db = get_db_session()
    rows = (
        db.query(model)
          .join(User)
          .filter(User.is_active)
          .all()
    )
    matches = [r for r in rows if _normalize(r.user.name) == name_norm]
    return matches[0] if len(matches) == 1 else None

# —————————————————————————————————————————————————————————————————————
# Función mixta para sacar coach_id y player_id de un evento de Google
# —————————————————————————————————————————————————————————————————————
def _guess_ids(ev):
    """
    ESTRATEGIA HÍBRIDA INTELIGENTE:
    1) Extended properties (automático)
    2) Parsing híbrido: nombres + IDs opcionales  
    3) Solo nombres (fuzzy)
    4) Solo IDs (#C #P)
    """
    props = ev.get("extendedProperties", {}).get("private", {})
    
    # 1) Extended properties (solo si válidos)
    cid = _safe_int(props.get("coach_id"))
    pid = _safe_int(props.get("player_id"))
    if cid and pid and cid < 100 and pid < 100:
        return cid, pid

    summary = ev.get("summary", "") or ""
    
    # 2) PARSING HÍBRIDO: nombres + IDs opcionales
    # Limpiar prefijo "Sesión:" / "Session:"
    summary_clean = re.sub(r'^(?:sesión|session)[:\-]\s*', '', summary, flags=re.IGNORECASE)
    
    # Buscar patrón: [algo] × [algo] o [algo] x [algo]
    match = re.search(r"(.+?)\s*[×x]\s*(.+)", summary_clean, re.IGNORECASE)
    
    if match:
        left_part = match.group(1).strip()   # Lado coach
        right_part = match.group(2).strip()  # Lado player
        
        coach_id = player_id = None
        
        # ANALIZAR LADO COACH (izquierda)
        coach_id_match = re.search(r"#[Cc](\d+)", left_part)
        if coach_id_match:
            # Hay ID explícito → usarlo
            coach_id = int(coach_id_match.group(1))
        else:
            # No hay ID → buscar por nombre
            coach_name = left_part.strip()
            coach_name_norm = _normalize(coach_name)
            coach_obj = _find_unique(Coach, coach_name_norm)
            if coach_obj:
                coach_id = coach_obj.coach_id
        
        # ANALIZAR LADO PLAYER (derecha)  
        player_id_match = re.search(r"#[Pp](\d+)", right_part)
        if player_id_match:
            # Hay ID explícito → usarlo
            player_id = int(player_id_match.group(1))
        else:
            # No hay ID → buscar por nombre
            player_name = right_part.strip()
            player_name_norm = _normalize(player_name)
            player_obj = _find_unique(Player, player_name_norm)
            if player_obj:
                player_id = player_obj.player_id
        
        # Si encontramos ambos, devolver
        if coach_id and player_id:
            return coach_id, player_id
    
    # 3) FALLBACK: Solo IDs tradicionales #C #P (anywhere en título)
    cid = (_extract_id(summary, r"#C(\d+)") or
           _extract_id(summary, r"Coach[#\s]*(\d+)"))
    pid = (_extract_id(summary, r"#P(\d+)") or
           _extract_id(summary, r"Player[#\s]*(\d+)"))
    if cid and pid:
        return cid, pid

    return None, None

# ---------- DB → Calendar ----------
def push_session(session: Session, db: AlchSession | None = None):
    # 1️⃣ usar la misma conexión que la instancia, si existe
    db = db or object_session(session) or get_db_session()

    body = _build_body(session)
    ev   = _service().events().insert(
        calendarId=CAL_ID, body=body).execute()

    session.calendar_event_id = ev["id"]
    db.add(session)          # asegura que está en la Sesión activa
    db.commit()              # persiste el cambio
    db.refresh(session)      # opcional: recarga para la UI

# --------------------------------------------------------------------------
#  ACTUALIZAR una sesión existente
def update_session(session: Session):
    """
    Sincroniza todos los cambios de una sesión existente con Google Calendar:
      • Nuevos summary, dates, notas, color…
      • Si el evento no existe (404), lo recrea.
    """
    db = get_db_session()
    # Si no teníamos event_id, lo empujamos como nuevo
    if not session.calendar_event_id:
        return push_session(session)

    # Construye el body con resumen, fechas, notas y color
    body = _build_body(session)
    try:
        _service().events().patch(
            calendarId=CAL_ID,
            eventId=session.calendar_event_id,
            body=body
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            # Evento borrado manualmente en GCal → lo recreamos
            push_session(session)
        else:
            raise
    else:
        # Asegúrate de persistir en BD cualquier cambio de event_id nuevo
        db.commit()

# --------------------------------------------------------------------------
#  BORRAR una sesión
def delete_session(session: Session):
    """
    Borra el evento de Calendar si existe y devuelve True/False
    según se haya eliminado o no.
    """
    if not session.calendar_event_id:
        return False
    try:
        _service().events().delete(
            calendarId=CAL_ID,
            eventId=session.calendar_event_id
        ).execute()
        return True
    except HttpError as e:                 # ya no existe → ignoramos
        if e.resp.status != 404:
            raise
        return False

# --------------------------------------------------------------------------
#  UTILIDAD compartida
def _build_body(session: Session) -> dict:
    """Devuelve el diccionario body que Calendar API espera."""
    return {
        "summary": (
            f"Session: {session.coach.user.name} × {session.player.user.name} "
            f"#C{session.coach_id} #P{session.player_id}"
        ),
        "description": session.notes or "",
        "start": {"dateTime": session.start_time.astimezone(dt.timezone.utc).isoformat()},
        "end":   {"dateTime": session.end_time.astimezone(dt.timezone.utc).isoformat()},
        "colorId": COLOR[session.status.value],
        "extendedProperties": {
            "private": {
                "session_id": str(session.id),
                "coach_id":   str(session.coach_id),
                "player_id":  str(session.player_id),
            }
        },
    }

def patch_color(event_id: str, status: SessionStatus):
    _service().events().patch(
        calendarId=CAL_ID, eventId=event_id,
        body={"colorId": COLOR[status.value]}
    ).execute()

def patch_event_after_import(session: Session, event_id: str):
    """
    Parcha un evento importado: añade IDs y formatea el título.
    OPTIMIZADO: Solo si realmente es necesario.
    """
    try:
        # Verificar si el evento ya tiene los datos correctos
        current_event = _service().events().get(calendarId=CAL_ID, eventId=event_id).execute()
        
        props = current_event.get("extendedProperties", {}).get("private", {})
        session_id_in_event = props.get("session_id")
        
        # Si ya tiene el session_id correcto, no hacer nada
        if session_id_in_event == str(session.id):
            logger.debug(f"✅ Evento {event_id[:8]}... ya tiene datos correctos")
            return
        
        # Solo patchear si realmente es necesario
        db = get_db_session()
        try:
            coach_name = db.query(User.name).join(Coach).filter(Coach.coach_id == session.coach_id).scalar()
            player_name = db.query(User.name).join(Player).filter(Player.player_id == session.player_id).scalar()

            patch_body = {
                "summary": f"Sesión: {coach_name} × {player_name}  #C{session.coach_id} #P{session.player_id}",
                "extendedProperties": {
                    "private": {
                        "session_id": str(session.id),
                        "coach_id": str(session.coach_id),
                        "player_id": str(session.player_id),
                    }
                }
            }

            _service().events().patch(
                calendarId=CAL_ID,
                eventId=event_id,
                body=patch_body
            ).execute()
            
            logger.info(f"🔧 Evento {event_id[:8]}... actualizado correctamente")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Error actualizando evento {event_id[:8]}...: {e}")

# ---------- DB → Calendar ----------   
def sync_db_to_calendar():
    """
    Recorre todas las sesiones en BD y:
      - push_session() si no tienen calendar_event_id
      - update_session() si ya lo tienen
    Devuelve (pushed, updated).
    """
    db = get_db_session()
    pushed = updated = 0

    for ses in db.query(Session).all():
        if not ses.calendar_event_id:
            push_session(ses)
            pushed += 1
        else:
            update_session(ses)
            updated += 1

    return pushed, updated

# ---------- Calendar → DB ----------
#@st.cache_data(ttl=int(os.getenv("SYNC_INTERVAL_MIN", "5")) * 60, show_spinner=False)
def sync_calendar_to_db():
    """Sincroniza eventos de Google Calendar hacia la base de datos con logging detallado."""
    start_time = time.time()
    logger.info("🔄 INICIANDO sincronización Calendar → BD")
    
    svc = _service()
    db = get_db_session()
    
    try:
        imported = updated = deleted = 0
        seen_ev_ids: set[str] = set()

        now = dt.datetime.now(dt.timezone.utc)
        win_start = now - dt.timedelta(days=30)
        win_end   = now + dt.timedelta(days=60)
        
        logger.info(f"📅 Ventana de sincronización: {win_start.date()} a {win_end.date()}")

        # Obtener eventos de Google Calendar
        logger.info("📡 Obteniendo eventos de Google Calendar...")
        events_response = svc.events().list(
            calendarId=CAL_ID,
            timeMin=win_start.isoformat(),
            timeMax=win_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        events = events_response.get("items", [])
        logger.info(f"📋 Encontrados {len(events)} eventos en Google Calendar")

        def _to_dt(iso: str) -> dt.datetime:
            return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))

        # Cargar todas las sesiones con calendar_event_id ya guardado
        logger.info("🗄️ Cargando sesiones existentes de la BD...")
        db_sessions = {
            s.calendar_event_id: s
            for s in db.query(Session)
                        .filter(Session.calendar_event_id != None)
                        .all()
        }
        logger.info(f"💾 Encontradas {len(db_sessions)} sesiones con event_id en BD")

        # Procesar cada evento de Google Calendar
        for i, ev in enumerate(events, 1):
            ev_id = ev["id"]
            seen_ev_ids.add(ev_id)
            
            if i % 10 == 0:  # Log progreso cada 10 eventos
                logger.info(f"⏳ Procesando evento {i}/{len(events)}")

            props = ev.get("extendedProperties", {}).get("private", {})
            sess_id = props.get("session_id")
            start_dt = _to_dt(ev["start"]["dateTime"])
            end_dt = _to_dt(ev["end"]["dateTime"])
            status = _status_from_color(ev.get("colorId", "9"))
            
            # ================================================================
            # BÚSQUEDA DE SESIÓN EXISTENTE - LÓGICA IMPLEMENTADA
            # ================================================================
            ses = None
            
            # 1. Buscar por session_id en extended properties
            if sess_id and sess_id.isdigit():
                ses = db.get(Session, int(sess_id))
                if ses:
                    logger.debug(f"✅ Encontrada por session_id: {sess_id}")
            
            # 2. Buscar por calendar_event_id (MÁS COMÚN)
            if not ses:
                ses = db_sessions.get(ev_id)
                if ses:
                    logger.debug(f"✅ Encontrada por event_id: {ev_id}")
            
            # 3. BÚSQUEDA FUZZY como último recurso
            if not ses:
                coach_id, player_id = _guess_ids(ev)
                if coach_id and player_id:
                    # Buscar sesión sin event_id que coincida en fecha/coach/player
                    potential_matches = db.query(Session).filter(
                        Session.coach_id == coach_id,
                        Session.player_id == player_id,
                        Session.calendar_event_id == None,
                        func.date(Session.start_time) == start_dt.date()
                    ).all()
                    
                    if potential_matches:
                        ses = potential_matches[0]
                        ses.calendar_event_id = ev_id  # Vincular evento
                        logger.info(f"🔗 MATCH FUZZY: Sesión #{ses.id} vinculada al evento {ev_id[:8]}...")
                        db.add(ses)
                        db.flush()
            
            # ================================================================
            # PROCESAMIENTO SEGÚN SI EXISTE O NO
            # ================================================================
            if ses:
                # ACTUALIZAR SESIÓN EXISTENTE
                changed = False
                changes = []
                
                # Estrategia: Calendar wins
                if ses.status != status:
                    changes.append(f"status: {ses.status.value} → {status.value}")
                    ses.status = status
                    changed = True

                db_start = ses.start_time.astimezone(dt.timezone.utc).replace(microsecond=0)
                new_start = start_dt.astimezone(dt.timezone.utc).replace(microsecond=0)
                if db_start != new_start:
                    changes.append(f"start: {db_start.strftime('%H:%M')} → {new_start.strftime('%H:%M')}")
                    ses.start_time = start_dt
                    changed = True

                db_end = ses.end_time.astimezone(dt.timezone.utc).replace(microsecond=0)
                new_end = end_dt.astimezone(dt.timezone.utc).replace(microsecond=0)
                if db_end != new_end:
                    changes.append(f"end: {db_end.strftime('%H:%M')} → {new_end.strftime('%H:%M')}")
                    ses.end_time = end_dt
                    changed = True
                
                # Actualizar notas si han cambiado
                new_notes = ev.get("description", "") or ""
                if (ses.notes or "") != new_notes:
                    changes.append("notes updated")
                    ses.notes = new_notes if new_notes else None
                    changed = True

                if changed:
                    logger.info(f"🔄 ACTUALIZADA Sesión #{ses.id}: {', '.join(changes)}")
                    db.add(ses)
                    updated += 1
                else:
                    logger.debug(f"✅ Sesión #{ses.id} sin cambios")
                    
            else:
                # CREAR NUEVA SESIÓN CON VALIDACIÓN
                logger.info(f"🆕 Creando sesión nueva: {ev.get('summary', 'Sin título')}")
                coach_id, player_id = _guess_ids(ev)
                
                if coach_id is None or player_id is None:
                    logger.warning(f"⚠️ No se pudo mapear evento - coach_id: {coach_id}, player_id: {player_id}")
                    continue

                # VALIDAR QUE COACH Y PLAYER EXISTEN EN BD
                coach_exists = db.query(Coach).filter(Coach.coach_id == coach_id).first()
                player_exists = db.query(Player).filter(Player.player_id == player_id).first()
                
                if not coach_exists:
                    logger.warning(f"⚠️ Coach ID {coach_id} no existe en BD - ignorando evento")
                    continue
                    
                if not player_exists:
                    logger.warning(f"⚠️ Player ID {player_id} no existe en BD - ignorando evento")
                    continue

                logger.info(f"✅ Mapeado y validado - Coach ID: {coach_id}, Player ID: {player_id}")
                
                new_session = Session(
                    coach_id=coach_id,
                    player_id=player_id,
                    start_time=start_dt,
                    end_time=end_dt,
                    status=status,
                    notes=ev.get("description"),
                    calendar_event_id=ev_id,
                    source="calendar",
                    version=1
                )
                
                db.add(new_session)
                db.flush()

                # Actualizar formato del evento en Calendar
                try:
                    patch_event_after_import(new_session, ev_id)
                    logger.debug(f"🔧 Evento {ev_id[:8]}... actualizado")
                except Exception as e:
                    logger.error(f"❌ Error actualizando evento en Calendar: {e}")

                imported += 1

        # ================================================================
        # DETECTAR ELIMINACIONES - LÓGICA CORREGIDA
        # ================================================================
        logger.info("🗑️ Verificando eventos eliminados...")

        # Sesiones en ventana que DEBERÍAN tener eventos correspondientes
        sessions_in_window = db.query(Session).filter(
            Session.calendar_event_id != None,
            Session.start_time >= win_start,
            Session.start_time <= win_end
        ).all()

        # Crear dict de sesiones EN LA VENTANA
        window_sessions = {s.calendar_event_id: s for s in sessions_in_window}

        # Candidatos: event_ids de BD que NO aparecieron en la búsqueda de Calendar
        elimination_candidates = [
            ev_id for ev_id in window_sessions.keys() 
            if ev_id not in seen_ev_ids
        ]

        logger.info(f"🔍 Sesiones en ventana: {len(window_sessions)}")
        logger.info(f"🔍 Candidatos para eliminación: {len(elimination_candidates)}")

        # NUEVA ESTRATEGIA: Si no aparece en la búsqueda de la ventana = eliminado
        if elimination_candidates:
            for ev_id in elimination_candidates:
                ses = window_sessions[ev_id]
                
                # Si el evento no apareció en la búsqueda dentro de la ventana de tiempo,
                # y la sesión SÍ está en esa ventana, entonces fue eliminado
                logger.info(f"🗑️ ELIMINANDO sesión #{ses.id} - evento {(ev_id[:8] if ev_id else 'N/A')}... no encontrado en ventana")
                db.delete(ses)
                deleted += 1

        if deleted == 0:
            logger.info("✅ No hay eventos para eliminar")

        # Commit final
        db.commit()
        
        elapsed_time = time.time() - start_time
        events_per_second = len(events) / elapsed_time if elapsed_time > 0 else 0

        logger.info(f"✅ SYNC COMPLETADA en {elapsed_time:.2f}s ({events_per_second:.1f} eventos/seg)")
        logger.info(f"📊 Resultados: {imported} importadas, {updated} actualizadas, {deleted} eliminadas")

        return imported, updated, deleted
        
    except Exception as e:
        logger.error(f"❌ ERROR durante sincronización: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _status_from_color(color: str) -> SessionStatus:
    """
    Dado un colorId de Google Calendar, devuelve el estado correspondiente.
    • Reds → CANCELED
    • Greens → COMPLETED
    • El resto → SCHEDULED
    """
    cid = str(color)

    # 1) Todos los rojos → canceled
    red_ids = {"11", "6", "5"}  # ajusta aquí si usas varios tonos de rojo
    if cid in red_ids:
        return SessionStatus.CANCELED

    # 2) Todos los verdes → completed
    green_ids = {"2", "10", "12", "13"}  # tonos de verde en tu paleta
    if cid in green_ids:
        return SessionStatus.COMPLETED

    # 3) El resto → scheduled
    return SessionStatus.SCHEDULED

def update_past_sessions():
    db = get_db_session()
    now = dt.datetime.now(dt.timezone.utc)
    todo = db.query(Session).filter(
        Session.status == SessionStatus.SCHEDULED,
        Session.end_time <= now
    ).all()
    for s in todo:
        s.status = SessionStatus.COMPLETED
        if s.calendar_event_id:
            patch_color(s.calendar_event_id, s.status)
    if todo:
        db.commit()
    return len(todo)

def get_sessions(
    start: dt.datetime,
    end: dt.datetime,
    coach_id: int | None = None,
    player_id: int | None = None,
    statuses: list[SessionStatus] | None = None,
):
    # Devuelve las sesiones filtradas y ordenadas por fecha de inicio.

    db = get_db_session()
    q = db.query(Session).filter(Session.start_time >= start,
                                 Session.start_time <= end)
    if coach_id:
        q = q.filter(Session.coach_id == coach_id)
    if player_id:
        q = q.filter(Session.player_id == player_id)
    if statuses:
        q = q.filter(Session.status.in_(statuses))
    return q.order_by(Session.start_time.asc()).all()

import hashlib  # ← Asegurar que está importado

def _calculate_session_hash(session: Session) -> str:
    """Calcula hash basado en datos importantes de la sesión."""
    data = (
        f"{session.coach_id}|{session.player_id}|"
        f"{session.start_time.isoformat()}|{session.end_time.isoformat()}|"
        f"{session.status.value}|{session.notes or ''}"
    )
    return hashlib.md5(data.encode()).hexdigest()

def _calculate_event_hash(ev: dict) -> str:
    """Calcula hash basado en datos importantes del evento de Calendar."""
    start_dt = dt.datetime.fromisoformat(ev["start"]["dateTime"].replace("Z", "+00:00"))
    end_dt = dt.datetime.fromisoformat(ev["end"]["dateTime"].replace("Z", "+00:00"))
    status = _status_from_color(ev.get("colorId", "9"))
    
    props = ev.get("extendedProperties", {}).get("private", {})
    coach_id = props.get("coach_id", "")
    player_id = props.get("player_id", "")
    
    data = (
        f"{coach_id}|{player_id}|"
        f"{start_dt.isoformat()}|{end_dt.isoformat()}|"
        f"{status.value}|{ev.get('description', '') or ''}"
    )
    return hashlib.md5(data.encode()).hexdigest()

def _update_session_tracking(session: Session):
    """Actualiza campos de tracking después de cambios."""
    session.sync_hash = _calculate_session_hash(session)
    session.updated_at = dt.datetime.now(dt.timezone.utc)
    session.last_sync_at = dt.datetime.now(dt.timezone.utc)
    session.is_dirty = False
    session.version += 1