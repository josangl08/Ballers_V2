# main.py
import streamlit as st
import importlib
import os
import logging

from common.login import login_page
from controllers.auth_controller import AuthController
from common.menu import create_sidebar_menu, get_content_path
from controllers.sync_coordinator import is_auto_sync_running, start_auto_sync
from controllers.db import initialize_database 

# Importar configuración
from config import STYLES_DIR, APP_NAME, APP_ICON, CSS_FILE, log_config_info

# Añadir TEMPORALMENTE al inicio de main.py (después de los imports)

# 🔍 DEBUG TEMPORAL - ELIMINAR DESPUÉS
if st.sidebar.button("🔍 DEBUG - Diagnosticar BD"):
    st.write("🔍 **DIAGNÓSTICO DE BASE DE DATOS**")
    
    import os
    import hashlib
    from sqlalchemy import text
    from controllers.db import get_db_session
    
    # Variables de entorno
    database_url = os.getenv("DATABASE_URL")
    database_path = os.getenv("DATABASE_PATH", "data/ballers_app.db")
    
    st.write(f"📊 DATABASE_URL: {'✅ Configurada' if database_url else '❌ No configurada'}")
    st.write(f"📁 DATABASE_PATH: {database_path}")
    
    if database_url:
        st.write(f"🔗 URL: {database_url[:50]}...")
        st.success("🔄 Debería usar Supabase")
    else:
        st.warning("🔄 Usando SQLite local")
    
    # Conectar y verificar
    try:
        db = get_db_session()
        
        # Buscar admin
        result = db.execute(text("""
            SELECT user_id, username, name, email, password_hash 
            FROM users 
            WHERE username = 'admin'
        """)).fetchone()
        
        if result:
            user_id, username, name, email, stored_hash = result
            st.success(f"✅ Usuario admin encontrado: {name} ({email})")
            st.write(f"🔐 Hash: {stored_hash[:20]}...")
            
            # Verificar hash
            test_hash = hashlib.sha256("admin123".encode()).hexdigest()
            if test_hash == stored_hash:
                st.success("✅ Hash correcto")
            else:
                st.error("❌ Hash incorrecto")
                st.write(f"Calculado: {test_hash[:20]}...")
                st.write(f"Almacenado: {stored_hash[:20]}...")
        else:
            st.error("❌ Usuario admin NO encontrado")
            
            # Listar usuarios
            users = db.execute(text("SELECT username, name FROM users LIMIT 5")).fetchall()
            if users:
                st.write("📋 Usuarios en BD:")
                for u, n in users:
                    st.write(f"- {u} ({n})")
        
        db.close()
        
    except Exception as e:
        st.error(f"❌ Error: {e}")

# 🔍 FIN DEBUG TEMPORAL
# 🆕 NUEVO: Registrar información del entorno al inicio
log_config_info()

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

    # Configurar nivel de logging basado en variable de entorno
    DEBUG_MODE = os.getenv("DEBUG", "False") == "True"
    
    if DEBUG_MODE:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        print("🔧 DEBUG MODE ENABLED - Verbose logging active")
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    # Inicializar base de datos
    try:
        if not initialize_database():
            st.error("❌ Critical error: Failed to initialise database")
            st.info("💡 Suggested solutions:")
            st.info("1. Run `python data/check_database.py` to diagnose")
            st.info("2. Verify write permissions on the `data/` folder")
            st.info("3. Run `python data/seed_database.py` to recreate the database")
            st.stop()
    except Exception as e:
            st.error(f"❌ Error initializing application: {str(e)}")
            st.stop()
    
    with AuthController() as auth:
        # Intentar restaurar sesión desde URL si no hay sesión activa
        if not auth.is_logged_in():
            success, message = auth.restore_session_from_url()
            if success:
                print(f"Auto-login: {message}")
        
        # Verificar si hay sesión activa
        has_session = auth.is_logged_in()
    
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
        
        # Verificar redirección forzada (necesario para que funcione)
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
                
            
if __name__ == "__main__":
    main()