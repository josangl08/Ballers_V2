# pages/ballers.py
from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.express as px
import datetime as dt

from controllers.player_controller import PlayerController, get_player_profile_data, get_players_for_list, update_player_notes_simple
from controllers.session_controller import SessionController
from controllers.internal_calendar import show_calendar
from models import SessionStatus
from controllers.validation_controller import ValidationController


def show_player_profile(player_id=None):
    """Muestra el perfil de un jugador específico"""
    
    # Obtener datos usando controller
    user_id = st.session_state.get("user_id") if st.session_state.get("user_type") == "player" else None
    profile_data = get_player_profile_data(player_id=player_id, user_id=user_id)
    
    if not profile_data:
        st.error("No player information found.")
        return
    
    player = profile_data["player"]
    user = profile_data["user"]
    stats = profile_data["stats"]
    test_results = profile_data["test_results"]
    
    # Mostrar información del perfil
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.image(user.profile_photo, width=200)
    
    with col2:
        st.title(f"{user.name}")
        st.write(f"**Email:** {user.email}")
        if user.phone:
            st.write(f"**Tel:** {user.phone}")
        if user.line:
            st.write(f"**LINE:** {user.line}")
        if stats["age"]:
            st.write(f"**Age:** {stats['age']} years")
        
        st.write(f"**Services:** {player.service}")
        st.write(f"**Enrollment Sessions:** {player.enrolment}")
        st.write(f"**Next Session:** {stats['next_session']}")

    st.divider()

    # Métricas usando stats calculadas
    colA, colB, colC = st.columns(3)
    colA.metric("Completed", stats["completed"])
    colB.metric("Scheduled", stats["scheduled"])
    colC.metric("Remaining", stats["remaining"])

    st.subheader(f"Calendar of {user.name}")

    # Filtros de fecha
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "From", 
            value=dt.datetime.now().date() - dt.timedelta(days=7),
        )
    with col2:
        end_date = st.date_input(
            "To", 
            value=dt.datetime.now().date() + dt.timedelta(days=7),
        )
    
    # Filtro de estado
    status_values = [s.value for s in SessionStatus]
    status_filter = st.multiselect(
        "Status", 
        options=status_values,
        default=status_values,
    )   

    # Usar ValidationController en lugar de duplicación
    is_valid, error = ValidationController.validate_date_range(start_date, end_date)
    if not is_valid:
        st.error(error)
        return

    # Usar SessionController para obtener y formatear sesiones
    with SessionController() as session_controller:
        sessions = session_controller.get_sessions_for_display(
            start_date=start_date,
            end_date=end_date,
            player_id=player.player_id,
            status_filter=status_filter
        )
        
        # Mostrar calendario
        show_calendar("", sessions, key="player_cal")
        
        # Mostrar listado de sesiones
        st.subheader("Sessions List")
        
        if not sessions:
            st.info(f"There are no scheduled sessions between {start_date.strftime('%d/%m/%Y')} and {end_date.strftime('%d/%m/%Y')}.")
        else:
            # Usar formateo unificado del SessionController
            formatted_data = session_controller.format_sessions_for_table(sessions)
            df = pd.DataFrame(formatted_data)
            
            # Aplicar estilos
            def style_sessions(row):
                if row["Status"] == "completed":
                    return ["background-color: rgba(76, 175, 80, 0.2)"] * len(row)
                elif row["Status"] == "canceled":
                    return ["background-color: rgba(244, 67, 54, 0.2)"] * len(row)
                elif row["Status"] == "scheduled":
                    return ["background-color: rgba(33, 150, 243, 0.2)"] * len(row)
                return [""] * len(row)

            styled_df = df.style.apply(style_sessions, axis=1)
            
            st.dataframe(
                styled_df, 
                column_config={
                    "ID": st.column_config.NumberColumn(width="small"),
                    "Coach": st.column_config.TextColumn(width="medium"),
                    "Player": st.column_config.TextColumn(width="medium"),
                    "Date": st.column_config.TextColumn(width="small"),
                    "Start Time": st.column_config.TextColumn(width="small"),
                    "End Time": st.column_config.TextColumn(width="small"),
                    "Status": st.column_config.TextColumn(width="small")
                },
                hide_index=True
            )
    
    # Mostrar pestañas con información adicional
    tab1, tab2 = st.tabs(["Test Results", "Notes"])
    
    with tab1:
        if test_results:
            # Usar PlayerController para formatear datos de tests
            with PlayerController() as player_controller:
                test_data = player_controller.format_test_data_for_chart(test_results)
                metrics_list = player_controller.get_test_metrics_list()
            
            df = pd.DataFrame(test_data)
            
            # Mostrar gráfico de evolución
            st.subheader("Performance Evolution")
            selected_metrics = st.multiselect(
                "Select metrics for visualization", 
                options=metrics_list,
                default=metrics_list[:3]
            )
            
            if selected_metrics:
                fig = px.line(
                    df, 
                    x="Date", 
                    y=selected_metrics,
                    title="Evolution of performance metrics",
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Mostrar tabla de resultados
            st.subheader("History of Tests")
            for i, test in enumerate(test_results):
                with st.expander(f"Test of {test.date.strftime('%d/%m/%Y')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Test Name:** {test.test_name}")
                        st.write(f"**Weight:** {test.weight} kg")
                        st.write(f"**Height:** {test.height} cm")
                    with col2:
                        st.write(f"**Ball Control:** {test.ball_control}")
                        st.write(f"**Control & Passing:** {test.control_pass}")
                        st.write(f"**Receiving & Passing/Scanning:** {test.receive_scan}")
                        st.write(f"**Dribling & Ball Carriying:** {test.dribling_carriying}")
                        st.write(f"**Shoot & Finishing:** {test.shooting}")
                        st.write(f"**Crossbar:** {test.crossbar}")
                        st.write(f"**Sprint:** {test.sprint}")
                        st.write(f"**T-test:** {test.t_test}")
                        st.write(f"**Jumping:** {test.jumping}")
        else:
            st.info("No test results available.")
    
    with tab2:
        st.subheader("Notes")
        if player.notes:
            st.write(player.notes)
        else:
            st.info("No notes available.")
            
        # Si el usuario es coach o admin, permitir añadir notas
        if st.session_state.get("user_type") in ["coach", "admin"]:
            new_note = st.text_area("Add/Edit notes:", value=player.notes or "")
            if st.button("Save notes"):
                # Usar función simplificada del controller
                success, message = update_player_notes_simple(player.player_id, new_note)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def show_player_list():
    """Muestra una lista de jugadores para coaches y admins - SIMPLIFICADO."""
    
    # Filtros de UI
    search_name = st.text_input("Search Player by name:")
    
    # Obtener datos usando controller
    players_data = get_players_for_list(search_term=search_name)
    
    if not players_data:
        if search_name:
            st.info(f"No players found matching '{search_name}'.")
        else:
            st.info("No registered players.")
        return
    
    # Mostrar jugadores en tarjetas - UI SOLO
    cols = st.columns(3)
    for i, player_data in enumerate(players_data):
        with cols[i % 3]:
            with st.container(border=True):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(player_data["profile_photo"], width=100)
                with col2:
                    st.write(f"**{player_data['name']}**")
                    
                    if player_data["age"]:
                        st.write(f"**Age:** {player_data['age']} years")
                    st.write(f"**Service:** {player_data['service']}")
                    st.write(f"**Sessions:** {player_data['enrolment']}")
                    st.write(f"**Remaining:** {player_data['remaining']}")
                    st.write(f"**Next Session:** {player_data['next_session']}")

                if st.button("View Profile", key=f"player_{player_data['player_id']}"):
                    st.session_state["selected_player_id"] = player_data["player_id"]
                    st.rerun()


def show_content():
    """Función principal para mostrar el contenido de la sección Ballers."""
    st.markdown('<h3 class="section-title">Profiles</h3>', unsafe_allow_html=True)
    
    # Si es un jugador, mostrar su propio perfil
    if st.session_state.get("user_type") == "player":
        show_player_profile()
    
    # Si es coach o admin, mostrar lista de jugadores o perfil seleccionado
    elif st.session_state.get("user_type") in ["coach", "admin"]:
        if "selected_player_id" in st.session_state:
            # Botón para volver a la lista
            if st.button("← Back to list"):
                del st.session_state["selected_player_id"]
                st.rerun()
            
            # Mostrar perfil del jugador seleccionado
            show_player_profile(st.session_state["selected_player_id"])
        else:
            # Mostrar lista de jugadores
            show_player_list()


if __name__ == "__main__":
    show_content()