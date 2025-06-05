# main.py
import streamlit as st
import importlib
import os
import logging

# Importar configuración
from config import STYLES_DIR, APP_NAME, APP_ICON, CSS_FILE

# Importar módulos personalizados
from common.login import login_page
from common.menu import create_sidebar_menu, get_content_path
from controllers.sync import run_sync_once, is_auto_sync_running, start_auto_sync
from controllers.db import initialize_database 

# Configuración de la página
st.set_page_config(
    page_title=APP_NAME,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Aplicar estilos personalizados
def load_css():
    try:
        # Asegurarse de que la carpeta existe
        os.makedirs(STYLES_DIR, exist_ok=True)
        
        # Si el archivo no existe, lo creamos
        if not os.path.exists(CSS_FILE):
            with open(CSS_FILE, "w") as f:
                f.write("""
/* Estilos básicos */
body {
    color: #333333;
    font-family: 'Roboto', sans-serif;
}

h1 {
    color: #1E88E5;
    font-weight: 700;
}

h2, h3 {
    color: #0D47A1;
    font-weight: 600;
}

.stButton>button {
    border-radius: 5px;
    font-weight: 500;
    background-color: #1E88E5;
    color: white;
}

.stButton>button:hover {
    background-color: #0D47A1;
}
                """)
            print(f"Archivo CSS creado en: {CSS_FILE}")
        
        # Leer y aplicar estilos
        with open(CSS_FILE, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
            
    except Exception as e:
        st.warning(f"No se pudo cargar el archivo de estilos: {str(e)}. Usando estilos por defecto.")
        # Aplicar estilos básicos si falla la carga del archivo
        st.markdown("""
        <style>
        body {color: #333333; font-family: 'Roboto', sans-serif;}
        h1 {color: #1E88E5; font-weight: 700;}
        h2, h3 {color: #0D47A1; font-weight: 600;}
        .stButton>button {border-radius: 5px; background-color: #1E88E5; color: white;}
        </style>
        """, unsafe_allow_html=True)

# Función principal
def main():
    # INICIALIZAR BASE DE DATOS AL INICIO
    try:
        if not initialize_database():
            st.error("❌ Error crítico: No se pudo inicializar la base de datos")
            st.info("💡 Soluciones sugeridas:")
            st.info("1. Ejecuta `python data/check_database.py` para diagnosticar")
            st.info("2. Verifica permisos de escritura en la carpeta `data/`")
            st.info("3. Ejecuta `python data/seed_database.py` para recrear la BD")
            st.stop()
    except Exception as e:
        st.error(f"❌ Error inicializando la aplicación: {str(e)}")
        st.stop()
    
    # Comprobar si ya hay un usuario en sesión antes de configurar la página
    has_session = "user_id" in st.session_state
    
    # Cargar estilos
    load_css()
    
    # Si no hay sesión, ocultar completamente el sidebar
    if not has_session:
        # Aplicar estilo para ocultar completamente el sidebar
        st.markdown("""
        <style>
        /* Ocultar control de sidebar */
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        
        /* Ocultar sidebar completamente */
        section[data-testid="stSidebar"] {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Mostrar página de login
        login_page()
        st.stop()
    else:
    
        # Auto-iniciar sincronización automática si es admin o coach  
        user_type = st.session_state.get("user_type")
        
        if user_type in ["admin", "coach"]:
            try:
                
                # Verificar si debe auto-iniciarse
                auto_start = st.session_state.get('auto_sync_auto_start', False)
                interval = st.session_state.get('auto_sync_interval', 5)
                
                # Auto-iniciar solo si está configurado y no está ya ejecutándose
                if auto_start and not is_auto_sync_running():
                    start_auto_sync(interval)
                    
            except ImportError:
                # Auto-sync no disponible, continuar normalmente
                pass
            except Exception:
                # Error silencioso para no afectar la app principal
                pass

        # Mostrar logo centrado
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("assets/ballers/logo_white.png", width=400)
       
        # Si hay sesión, mostrar menú y contenido según selección
        selected_section = create_sidebar_menu()
        
        # 🎯 VERIFICAR redirección forzada (necesario para que funcione)
        if "force_section" in st.session_state:
            selected_section = st.session_state["force_section"]
            del st.session_state["force_section"]  # Limpiar inmediatamente
        
        if selected_section:
            # Obtener la ruta del módulo para la sección seleccionada
            content_module_path = get_content_path(selected_section)
            
            if content_module_path:
                try:
                    # Importar dinámicamente el módulo de contenido
                    content_module = importlib.import_module(content_module_path)
                    
                    # Ejecutar la función principal del módulo
                    if hasattr(content_module, "show_content"):
                        content_module.show_content()
                    else:
                        st.error(f"El módulo {content_module_path} no tiene la función show_content")
                except ModuleNotFoundError:
                    st.error(f"No se encontró el módulo {content_module_path}...")
                except Exception as e:
                    st.error(f"Error al cargar el contenido: {str(e)}")
            else:
                st.warning("Sección no implementada")
                
       # run_sync_once()
            
if __name__ == "__main__":
    main()