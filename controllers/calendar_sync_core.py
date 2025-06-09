# controllers/calendar_sync_core.py
"""
Núcleo de sincronización con Google Calendar.
Maneja la sincronización bidireccional sin coordinar auto-sync ni estadísticas.
"""
import datetime as dt
import logging
import time
import re
from typing import List, Tuple, Dict, Optional
from sqlalchemy import func
from googleapiclient.errors import HttpError

from models import Session, SessionStatus, Coach, Player, User
from .session_controller import SessionController
from controllers.db import get_db_session
from controllers.google_client import calendar
from controllers.validation_controller import validate_session_for_import
from .calendar_utils import (
    calculate_session_hash,
    calculate_event_hash,
    normalize_text,
    extract_id_from_text,
    find_unique_user,
    safe_int,
    format_time_local,
    session_needs_update,
    update_session_tracking,
    build_calendar_event_body,
    status_from_color
)
from config import CALENDAR_COLORS, CALENDAR_ID

logger = logging.getLogger(__name__)
LOCAL_TZ = dt.timezone(dt.timedelta(hours=2))  # Madrid timezone simplificado

def guess_coach_player_ids(event: dict) -> Tuple[Optional[int], Optional[int]]:
    """
    ESTRATEGIA HÍBRIDA INTELIGENTE para extraer coach_id y player_id:
    1) Extended properties (automático)
    2) Parsing híbrido: nombres + IDs opcionales  
    3) Solo nombres (fuzzy)
    4) Solo IDs (#C #P)
    """
    props = event.get("extendedProperties", {}).get("private", {})
    
    # 1) Extended properties (solo si válidos)
    cid = safe_int(props.get("coach_id"))
    pid = safe_int(props.get("player_id"))
    if cid and pid and cid < 100 and pid < 100:
        return cid, pid

    summary = event.get("summary", "") or ""
    
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
            coach_name_norm = normalize_text(coach_name)
            coach_obj = find_unique_user(Coach, coach_name_norm)
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
            player_name_norm = normalize_text(player_name)
            player_obj = find_unique_user(Player, player_name_norm)
            if player_obj:
                player_id = player_obj.player_id
        
        # Si encontramos ambos, devolver
        if coach_id and player_id:
            return coach_id, player_id
    
    # 3) FALLBACK: Solo IDs tradicionales #C #P (anywhere en título)
    cid = (extract_id_from_text(summary, r"#C(\d+)") or
            extract_id_from_text(summary, r"Coach[#\s]*(\d+)"))
    pid = (extract_id_from_text(summary, r"#P(\d+)") or
            extract_id_from_text(summary, r"Player[#\s]*(\d+)"))
    if cid and pid:
        return cid, pid

    return None, None


def patch_event_after_import(session: Session, event_id: str):
    """
    Parcha un evento importado: añade IDs y formatea el título.
    OPTIMIZADO: Solo si realmente es necesario.
    """
    try:
        # Verificar si el evento ya tiene los datos correctos
        current_event = calendar().events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()
        
        props = current_event.get("extendedProperties", {}).get("private", {})
        session_id_in_event = props.get("session_id")
        current_color = current_event.get("colorId", "9")

        # Verificar si necesita actualización
        needs_update = False

        # Si no tiene session_id correcto
        if session_id_in_event != str(session.id):
            needs_update = True
        
        # Si tiene color desconocido, normalizarlo
        valid_colors = [v["google"] for v in CALENDAR_COLORS.values()]
        if current_color not in valid_colors:
            needs_update = True
            logger.info(f"🎨 Color desconocido {current_color} → normalizando a scheduled")
        
        # Si ya tiene el session_id correcto, no hacer nada
        if not needs_update:
            logger.debug(f"✅ Evento {event_id[:8]}... ya tiene datos correctos")
            return
        
        # Solo patchear si realmente es necesario
        db = get_db_session()
        try:
            coach_name = db.query(User.name).join(Coach).filter(Coach.coach_id == session.coach_id).scalar()
            player_name = db.query(User.name).join(Player).filter(Player.player_id == session.player_id).scalar()

            # Determinar color correcto basado en estado de sesión
            COLOR = {k: v["google"] for k, v in CALENDAR_COLORS.items()}
            correct_color = COLOR[session.status.value]

            patch_body = {
                "summary": f"Session: {coach_name} × {player_name}  #C{session.coach_id} #P{session.player_id}",
                "colorId": correct_color,  # Normalizar color
                "extendedProperties": {
                    "private": {
                        "session_id": str(session.id),
                        "coach_id": str(session.coach_id),
                        "player_id": str(session.player_id),
                    }
                }
            }

            calendar().events().patch(
                calendarId=CALENDAR_ID,
                eventId=event_id,
                body=patch_body
            ).execute()
            
            logger.info(f"🔧 Evento {event_id[:8]}... actualizado correctamente")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Error actualizando evento {event_id[:8]}...: {e}")


def update_session_in_calendar_only(session: Session):
    """Actualiza evento en Calendar sin tocar la sesión BD actual."""
    if not session.calendar_event_id:
        logger.warning(f"⚠️ Sesión #{session.id} sin event_id")
        return

    try:
        body = build_calendar_event_body(session)
        calendar().events().patch(
            calendarId=CALENDAR_ID,
            eventId=session.calendar_event_id,
            body=body
        ).execute()
        logger.debug(f"📤 Evento {session.calendar_event_id[:8]}... actualizado desde BD")
        
    except HttpError as e:
        if e.resp.status == 404:
            logger.warning(f"⚠️ Evento {session.calendar_event_id[:8]}... no existe en Calendar")
        else:
            logger.error(f"❌ Error actualizando evento en Calendar: {e}")
            raise


def sync_calendar_to_db_with_feedback() -> Tuple[int, int, int, List[Dict], List[Dict]]:
    """
    Sincroniza eventos de Google Calendar hacia la base de datos con logging detallado.
    
    Returns:
        Tuple (imported, updated, deleted, rejected_events, warning_events)
    """
    start_time = time.time()
    logger.info("🔄 INICIANDO sincronización Calendar → BD")
    
    svc = calendar()
    db = get_db_session()

    rejected_events = []  # Lista de eventos rechazados
    warning_events = []   # Lista de eventos con warnings
    
    try:
        imported = updated = deleted = 0
        seen_ev_ids: set[str] = set()

        now = dt.datetime.now(dt.timezone.utc)
        win_start = now - dt.timedelta(days=15)
        win_end   = now + dt.timedelta(days=30)
        
        logger.info(f"📅 Ventana de sincronización: {win_start.date()} a {win_end.date()}")

        # Obtener eventos de Google Calendar
        logger.info(f"📡 Obteniendo eventos de Google Calendar (ID: {CALENDAR_ID})...")
        events_response = svc.events().list(
            calendarId=CALENDAR_ID,
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
            status = status_from_color(ev.get("colorId", "9"))
            
            # Busqueda de sesion existente
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
                    logger.debug(f"✅ Encontrada por event_id: {ev_id[:8]}...")

            # Busqueda Fuzzy como último recurso
            if not ses:
                coach_id, player_id = guess_coach_player_ids(ev)
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

            if ses:
                # SESIÓN EXISTENTE - verificar cambios
                
                # 1. Verificar si event_id coincide
                if ses.calendar_event_id != ev_id:
                    logger.debug(f"🔗 Actualizando event_id: {ses.calendar_event_id} → {ev_id}")
                    ses.calendar_event_id = ev_id
                    db.add(ses)
                    db.flush()

                # 2. HASH COMPARISON - Prioridad máxima
                current_hash = ses.sync_hash or ""
                
                # Si no tiene hash, calcularlo ahora (sesión antigua)
                if not current_hash:
                    current_hash = calculate_session_hash(ses)
                    ses.sync_hash = current_hash
                    logger.debug(f"🔧 Hash inicial calculado para sesión #{ses.id}")

                event_hash = calculate_event_hash(ev)
                
                logger.debug(f"🔍 Hash check Sesión #{ses.id}: BD='{current_hash[:8]}...' vs Event='{event_hash[:8]}...'")
                
                # 3. Si hashes coinciden → NO HAY CAMBIOS REALES
                if current_hash == event_hash:
                    logger.debug(f"✅ Sesión #{ses.id} - hashes coinciden, sin cambios")
                    continue
                
                # 4. HASHES DIFERENTES → Hay cambios reales, decidir quién gana
                
                # 4a. Verificar si sesión está marcada como dirty (cambios locales pendientes)
                if hasattr(ses, 'is_dirty') and ses.is_dirty:
                    # Sesión local tiene cambios pendientes → APP WINS
                    logger.info(f"🔄 APP WINS - Sesión #{ses.id} (cambios locales pendientes)")
                    logger.info(f"📝 BD→CALENDAR: Forzando actualización de evento desde sesión #{ses.id}")
                    
                    try:
                        ses.is_dirty = False
                        ses.last_sync_at = dt.datetime.now(dt.timezone.utc)
                        update_session_in_calendar_only(ses)
                        logger.info(f"✅ Evento actualizado en Calendar desde BD (APP WINS)")
                    except Exception as e:
                        logger.error(f"❌ Error actualizando Calendar desde BD: {e}")
                        ses.is_dirty = True
                        db.add(ses)

                    continue
                
                # 4b. Análisis de timestamps (solo como tiebreaker)
                event_updated_str = ev.get("updated") or ev.get("created") or ""
                event_updated = None
                session_updated = ses.updated_at or ses.created_at
                
                calendar_wins = True  # Default: Calendar wins
                conflict_reason = "hash_different_calendar_default"
                
                if event_updated_str and session_updated:
                    try:
                        event_updated = dt.datetime.fromisoformat(event_updated_str.replace("Z", "+00:00"))
                        if event_updated.tzinfo is None:
                            event_updated = event_updated.replace(tzinfo=dt.timezone.utc)
                        
                        if session_updated and session_updated.tzinfo is None:
                            session_updated = session_updated.replace(tzinfo=dt.timezone.utc)
                        
                        time_diff = (session_updated - event_updated).total_seconds()
                        time_diff_abs = abs(time_diff)

                        # Solo usar timestamps para DIFERENCIAS SIGNIFICATIVAS (>10 segundos)
                        if time_diff_abs <= 10:  
                            logger.debug(f"✅ Sesión #{ses.id} - diferencia mínima ({int(time_diff)}s), sin cambios")
                            continue  
                            
                        # Solo procesar si diferencia > 10 segundos    
                        elif time_diff > 10:  
                            calendar_wins = False
                            conflict_reason = f"app_significantly_newer_by_{int(time_diff)}s"
                        else:
                            calendar_wins = True
                            conflict_reason = f"calendar_significantly_newer_by_{int(-time_diff)}s"
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Error calculando timestamps para sesión #{ses.id}: {e}")
                        calendar_wins = True
                        conflict_reason = "timestamp_error"
                else:
                    calendar_wins = True
                    conflict_reason = "no_timestamps"
                    
                # 5. APLICAR RESOLUCIÓN
                if calendar_wins:
                    logger.info(f"🔄 CALENDAR WINS - Sesión #{ses.id} ({conflict_reason})")
                    
                    is_valid, error_msg, warnings = validate_session_for_import(start_dt, end_dt)
    
                    if not is_valid:
                        # RECHAZAR update si es inválido
                        rejected_events.append({
                            "title": f"{ses.coach.user.name} × {ses.player.user.name}",
                            "date": start_dt.strftime("%d/%m/%Y"),
                            "time": f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}",
                            "reason": error_msg,
                            "suggestion": "Corregir horarios en Google Calendar"
                        })
                        logger.warning(f"🚫 UPDATE RECHAZADO - Sesión #{ses.id}: {error_msg}")
                        continue  # No actualizar, saltar al siguiente evento
                    
                    changed = False
                    changes = []

                    # Si hay warnings, agregar a lista
                    if warnings:
                        warning_events.append({
                            "title": f"{ses.coach.user.name} × {ses.player.user.name}",
                            "date": start_dt.strftime("%d/%m/%Y"),
                            "time": f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}",
                            "warnings": warnings
                        })
                        logger.warning(f"⚠️ SESIÓN ACTUALIZADA CON WARNINGS - #{ses.id}: {'; '.join(warnings)}") 

                    # Aplicar cambios del calendario
                    if ses.status != status:
                        changes.append(f"status: {ses.status.value} → {status.value}")
                        ses.status = status
                        changed = True

                    db_start = ses.start_time.astimezone(dt.timezone.utc).replace(microsecond=0)
                    new_start = start_dt.astimezone(dt.timezone.utc).replace(microsecond=0)
                    if db_start != new_start:
                        changes.append(f"start: {format_time_local(db_start)} → {format_time_local(new_start)}")
                        ses.start_time = start_dt
                        changed = True

                    db_end = ses.end_time.astimezone(dt.timezone.utc).replace(microsecond=0)
                    new_end = end_dt.astimezone(dt.timezone.utc).replace(microsecond=0)
                    if db_end != new_end:
                        changes.append(f"end: {format_time_local(db_end)} → {format_time_local(new_end)}")
                        ses.end_time = end_dt
                        changed = True
                    
                    new_notes = ev.get("description", "") or ""
                    if (ses.notes or "") != new_notes:
                        changes.append("notes")
                        ses.notes = new_notes if new_notes else None
                        changed = True

                    if changed:
                        update_session_tracking(ses)
                        logger.info(f"📝 CALENDAR→BD Sesión #{ses.id}: {', '.join(changes)}")
                        db.add(ses)
                        updated += 1
                    else:
                        logger.debug(f"✅ Sesión #{ses.id} sin cambios después de análisis")
                        
                else:
                    # APP WINS - actualizar Calendar desde BD
                    logger.info(f"🔄 APP WINS - Sesión #{ses.id} ({conflict_reason})")
                    logger.info(f"📝 BD→CALENDAR: Forzando actualización de evento desde sesión #{ses.id}")
                    
                    try:
                        ses.is_dirty = False
                        ses.last_sync_at = dt.datetime.now(dt.timezone.utc)
                        update_session_in_calendar_only(ses)
                        logger.info(f"✅ Evento actualizado en Calendar desde BD")
                    except Exception as e:
                        logger.error(f"❌ Error actualizando Calendar desde BD: {e}")
                        ses.is_dirty = True
                        db.add(ses)
                    
            else:
                # CREAR NUEVA SESIÓN CON VALIDACIÓN
                logger.info(f"🆕 Creando sesión nueva: {ev.get('summary', 'Sin título')}")
                coach_id, player_id = guess_coach_player_ids(ev)
                
                if coach_id is None or player_id is None:
                    rejected_events.append({
                        "title": ev.get("summary", "Sin título"),
                        "date": start_dt.strftime("%d/%m/%Y"),
                        "time": f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}",
                        "reason": "No se pudo identificar coach/player en el título",
                        "suggestion": "Verificar formato: 'Juan × María #C1 #P5'"
                    })
                    logger.warning(f"⚠️ No se pudo mapear evento - coach_id: {coach_id}, player_id: {player_id}")
                    continue

                # VALIDAR QUE COACH Y PLAYER EXISTEN EN BD
                coach_exists = db.query(Coach).filter(Coach.coach_id == coach_id).first()
                player_exists = db.query(Player).filter(Player.player_id == player_id).first()
                
                if not coach_exists:
                    rejected_events.append({
                        "title": ev.get("summary", "Sin título"),
                        "date": start_dt.strftime("%d/%m/%Y"),
                        "time": f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}",
                        "reason": f"Coach ID {coach_id} no existe en la base de datos",
                        "suggestion": "Verificar que el coach esté registrado en la aplicación"
                    })
                    logger.warning(f"⚠️ Coach ID {coach_id} no existe en BD - ignorando evento")
                    continue

                if not player_exists:
                    rejected_events.append({
                        "title": ev.get("summary", "Sin título"),
                        "date": start_dt.strftime("%d/%m/%Y"),
                        "time": f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}",
                        "reason": f"Player ID {player_id} no existe en la base de datos",
                        "suggestion": "Verificar que el player esté registrado en la aplicación"
                    })
                    logger.warning(f"⚠️ Player ID {player_id} no existe en BD - ignorando evento")
                    continue
                
                # VALIDACIÓN FLEXIBLE CON FEEDBACK AL USUARIO
                is_valid, error_msg, warnings = validate_session_for_import(start_dt, end_dt)
                
                if not is_valid:
                    # RECHAZADO - feedback al usuario
                    rejected_events.append({
                        "title": ev.get("summary", "Sin título"),
                        "date": start_dt.strftime("%d/%m/%Y"),
                        "time": f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}",
                        "reason": error_msg,
                        "suggestion": "Corregir horarios en Google Calendar y ejecutar sync manual"
                    })
                    logger.error(f"❌ EVENTO RECHAZADO - {ev.get('summary', 'Sin título')}: {error_msg}")
                    continue
                
                # IMPORTADO - verificar si tiene warnings
                if warnings:
                    warning_events.append({
                        "title": ev.get("summary", "Sin título"),
                        "date": start_dt.strftime("%d/%m/%Y"),
                        "time": f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}",
                        "warnings": warnings
                    })
                    logger.warning(f"⚠️ EVENTO CON WARNINGS - {ev.get('summary', 'Sin título')}: {'; '.join(warnings)}")
                else:
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

        # Detectar eliminaciones
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

        # Si no aparece en la búsqueda de la ventana = eliminado
        if elimination_candidates:
            for ev_id in elimination_candidates:
                ses = window_sessions[ev_id]
                
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

        # Log resumen de problemas
        if rejected_events:
            logger.warning(f"🚫 {len(rejected_events)} eventos rechazados por problemas críticos")
        if warning_events:
            logger.warning(f"⚠️ {len(warning_events)} eventos importados con advertencias")

        return imported, updated, deleted, rejected_events, warning_events
        
    except Exception as e:
        # MEJORAR LOGGING DE ERRORES
        if "403" in str(e):
            logger.error("❌ ERROR 403: Sin permisos para Google Calendar - verificar API keys")
        elif "404" in str(e):
            logger.error("❌ ERROR 404: Calendario no encontrado - verificar CALENDAR_ID")
        elif "JSON" in str(e) or "Expecting property name" in str(e):
            logger.error("❌ ERROR AUTH: Credenciales inválidas - verificar google_service_account.json")
        else:
            logger.error(f"❌ ERROR sincronización: {e}")
        
        db.rollback()
        raise
    finally:
        db.close()


def sync_calendar_to_db() -> Tuple[int, int, int]:
    """Función simplificada que solo devuelve estadísticas básicas (para auto-sync)."""
    imported, updated, deleted, rejected_events, warning_events = sync_calendar_to_db_with_feedback()
    
    # Solo loggar problemas pero no devolver las listas (para auto-sync simple)
    if rejected_events:
        logger.warning(f"🚫 Auto-sync rechazó {len(rejected_events)} eventos")
    if warning_events:
        logger.warning(f"⚠️ Auto-sync importó {len(warning_events)} eventos con advertencias")
    
    return imported, updated, deleted


def sync_db_to_calendar() -> Tuple[int, int]:
    """
    Sincroniza sesiones de BD hacia Google Calendar.
    🔧 CORREGIDO: Ahora respeta correctamente session_needs_update() y no actualiza innecesariamente.
    
    Returns:
        Tuple (pushed, updated)
    """
    
    with SessionController() as controller:
        db = controller.db
        pushed = updated = skipped = 0

        for ses in db.query(Session).all():
            if not ses.calendar_event_id:
                # Sin event_id → crear nuevo
                success = controller._push_session_to_calendar(ses)
                if success:
                    pushed += 1
                    logger.info(f"📤 NUEVO: Sesión #{ses.id} creada en Calendar")
            else:
                # 🔧 FIX: VERIFICAR SI REALMENTE NECESITA ACTUALIZACIÓN
                if session_needs_update(ses):
                    # Solo actualizar si realmente hay cambios
                    success = controller._update_session_in_calendar(ses)
                    if success:
                        updated += 1
                        logger.info(f"🔄 ACTUALIZADA: Sesión #{ses.id} actualizada en Calendar")
                    else:
                        logger.warning(f"❌ FALLO: Sesión #{ses.id} falló al actualizar")
                else:
                    skipped += 1
                    logger.debug(f"⏭️ OMITIDA: Sesión #{ses.id} sin cambios")

        # 🔧 MEJORADO: Log más detallado
        total_processed = pushed + updated + skipped
        logger.info(f"📊 Push BD→Calendar completado:")
        logger.info(f"   📤 {pushed} sesiones NUEVAS creadas")
        logger.info(f"   🔄 {updated} sesiones ACTUALIZADAS")  
        logger.info(f"   ⏭️ {skipped} sesiones OMITIDAS (sin cambios)")
        logger.info(f"   📋 {total_processed} sesiones procesadas")
        
        if updated > 10:
            logger.warning(f"⚠️ ADVERTENCIA: {updated} sesiones actualizadas - investigar por qué necesitan update")

        return pushed, updated


def patch_color(event_id: str, status: SessionStatus):
    """Actualiza solo el color de un evento en Calendar."""
    COLOR = {k: v["google"] for k, v in CALENDAR_COLORS.items()}
    
    calendar().events().patch(
        calendarId=CALENDAR_ID, eventId=event_id,
        body={"colorId": COLOR[status.value]}
    ).execute()