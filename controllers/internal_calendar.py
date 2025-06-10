from __future__ import annotations
import json
import datetime as dt
from zoneinfo import ZoneInfo
import streamlit as st
import streamlit.components.v1 as components
from models import Session
from common.utils import to_calendar_str
from config import CALENDAR_COLORS  
from config import TIMEZONE, TIMEZONE_NAME

HEX = {k: v["hex"] for k, v in CALENDAR_COLORS.items()}
TZ  = TIMEZONE

def _fmt_local(ts: dt.datetime) -> str:
    """ISO 8601 completo, conserva la zona (+07:00)"""
    return ts.isoformat(timespec="seconds")

def _to_event(s: Session) -> dict:
    return {
        "id":    s.id,
        "title": f"{s.coach.user.name} × {s.player.user.name}",
        "start": to_calendar_str(s.start_time),
        "end":   to_calendar_str(s.end_time) if s.end_time is not None else "",
        "description": s.notes or "",
        "player": s.player.user.name,
        "coach":  s.coach.user.name,
        "color":  HEX[s.status.value],
    }

def show_calendar(title: str, sessions, *, height: int = 650,
                  editable: bool = False, key: str = "calendar") -> None:

    st.subheader(title)
    events = json.dumps([_to_event(s) for s in sessions], default=str)
    html = f"""
<link  href="https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js"></script>

<div id="{key}"></div>

<script>
document.addEventListener("DOMContentLoaded", () => {{
  const root = document.getElementById("{key}");
  if (root.firstChild) return;                 // evita redibujar
  console.log("⚽ FullCalendar: mounting…");

  try {{
    const cal = new FullCalendar.Calendar(root, {{
        initialView: "timeGridWeek",
        headerToolbar: {{
            left:   "prev,next today",
            center: "title",
            right:  "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
        }},
        slotEventOverlap: false,   // NO permite que dos eventos solapen la ranura
        eventOverlap:     false,   // idem para overlaps parciales
        locale:  "en",
        timeZone:"TIMEZONE_NAME",
        height:  {height},
        slotMinTime: "08:00:00",
        slotMaxTime: "19:00:00",
        firstDay: 1,
        navLinks: true,
        editable: {str(editable).lower()},

        /* Formato 24 h para todas las vistas */
        eventTimeFormat: {{hour:'2-digit', minute:'2-digit', hourCycle:'h23'}},
        slotLabelFormat: {{hour:'2-digit', minute:'2-digit', hourCycle:'h23'}},
        listDayFormat:   {{weekday:'long', day:'numeric', month:'long'}},
        events:  {events},

        eventDidMount: ({{
            event: ev, el
        }}) => {{
        /* — tooltip — */
        const f = new Intl.DateTimeFormat("en-GB",{{ hour:'2-digit', minute:'2-digit', hourCycle:'h23'}});
        let html = `<span style=\"color:rgba(36,222,132,1)\"><strong>${{f.format(ev.start)}}–${{f.format(ev.end)}}</strong></span><br>
                    <span style=\"color:rgba(36,222,132,1)\">Player:</span> ${{ev.extendedProps.player}}<br>
                    <span style=\"color:rgba(36,222,132,1)\">Coach:</span> ${{ev.extendedProps.coach}}`;
        if (ev.extendedProps.description) html += `<br>${{ev.extendedProps.description}}`;

        const tip = Object.assign(document.createElement("div"), {{
          className: "fc-tip",
          innerHTML: html,
          style: `
            position:absolute; z-index:10001; background:#333; color:#fff;
            padding:8px; border:1px solid #555; border-radius:6px;
          `
        }});
        tip.hidden = true;

        el.addEventListener("mouseenter", () => {{
          tip.hidden = false; document.body.appendChild(tip);
        }});
        el.addEventListener("mouseleave", () => {{
          tip.hidden = true; if (document.body.contains(tip)) document.body.removeChild(tip);
        }});
        el.addEventListener("mousemove", e => {{
          tip.style.top  = e.pageY + "px";
          tip.style.left = e.pageX + "px";
        }});
      }}
    }});
    cal.render();
  }} catch (e) {{
    console.error("⚽ FullCalendar error →", e);
  }}
}});
</script>

<style>

/* CONTORNO del grid (todas las vistas) ------------------------------------*/
#{key} .fc-scrollgrid,
#{key} th, 
#{key} td        {{ border-color:#333; }}

/* CABECERA días -----------------------------------------------------------*/
#{key} .fc-col-header-cell         {{ background:#1F1F1F; color:#FAFAFA; }}
#{key} .fc-toolbar-title           {{ color:#FAFAFA; }}

/* BOTONES -----------------------------------------------------------------*/
#{key} .fc-button-primary,
#{key} .fc-button-primary:disabled {{background:#333; border:#333; color:rgba(36,222,132,1);    }}
#{key} .fc-button-primary:not(:disabled):hover,
#{key} .fc-button-primary:not(:disabled).fc-button-active {{background:#1DDD6E; border:#1DDD6E; color:#333; }}

/* HOY y eventos pasados ---------------------------------------------------*/
#{key} .fc-day-today {{ background:rgba(29,221,110,.1); }}
#{key} .fc-event-past {{ opacity:.4; }}

/* MES ---------------------------------------------------------------------*/
#{key} .fc-daygrid-event, 
#{key} .fc-daygrid-event-dot           {{ color:#FAFAFA;   }}
#{key} .fc-daygrid-day-frame           {{    }}
#{key} .fc-daygrid-event-harness       {{background: #333333; border: 1px solid rgba(250,250,250,0.5); margin: 2px; border-radius: 6px; }}
#{key} .fc-daygrid-event               {{margin: 0; border-radius: 6px;  }}
#{key} .fc-daygrid-event:hover         {{background: rgba(36,222,132,0.8) !important; border-color: rgba(36,222,132,1) !important; }}

/* SEMANA / DÍA ------------------------------------------------------------*/
#{key} .fc-timegrid-slot-label-cushion,
#{key} .fc-timegrid-axis-frame,
#{key} .fc-scrollgrid-sync-inner       {{ color:#FAFAFA;   }}
#{key} .fc-daygrid-day-events          {{ margin: 1px; }} 
#{key} .fc-timegrid-event:hover {{background: rgba(36,222,132,0.9) !important; border-color: rgba(36,222,132,1) !important; }}
#{key} .fc-timegrid-event-harness {{margin: 1.5px;  }}

/* LISTA -------------------------------------------------------------------*/
#{key} .fc-list, 
#{key} .fc-list-day-cushion            {{ background:#333333; color:#FAFAFA; }}
#{key} .fc-list-event                  {{background:#1D1B1A; color:#FAFAFA; border:1px solid #333;  }}
#{key} .fc-list-event:hover td {{background: rgba(36,222,132,1) !important; color: #333 !important; }}
#{key} .fc-list-event:hover a {{color: #333 !important; }}
</style>
"""
    components.html(html, height=height+70, scrolling=False)