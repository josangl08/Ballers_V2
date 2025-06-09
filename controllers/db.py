# controllers/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession
from models import Base
from config import DATABASE_PATH
import os
import streamlit as st
from typing import Optional

# Variables globales para reutilizar engine y Session
_engine = None
_Session: Optional[sessionmaker] = None

def initialize_database() -> bool:
    """
    Inicializa la base de datos solo una vez al inicio de la aplicación.
    
    Returns:
        bool: True si la inicialización fue exitosa, False en caso contrario
    """
    global _engine, _Session
    
    try:
        if _engine is None:
            # 🔧 PRIORIDAD: DATABASE_URL desde múltiples fuentes
            database_url = None
            
            # 1. Streamlit Secrets (para Streamlit Cloud) - PRIORIDAD MÁXIMA
            try:
                if hasattr(st, 'secrets') and hasattr(st.secrets, 'DATABASE_URL'):
                    database_url = st.secrets.DATABASE_URL
                    print("🔗 Usando DATABASE_URL de Streamlit secrets")
            except Exception as e:
                print(f"⚠️ No se pudo leer DATABASE_URL de secrets: {e}")
            
            # 2. Variable de entorno (.env) - SEGUNDA PRIORIDAD
            if not database_url:
                database_url = os.getenv("DATABASE_URL")
                if database_url:
                    print("🔗 Usando DATABASE_URL de variable de entorno")
            
            # 3. Decidir conexión
            if database_url:
                # 🚀 CONEXIÓN A SUPABASE (PRODUCCIÓN)
                _engine = create_engine(database_url)
                print("✅ Conectando a Supabase (PostgreSQL) - PRODUCCIÓN")
            else:
                # 🔧 CONEXIÓN LOCAL (DESARROLLO)
                # Validar que DATABASE_PATH no sea None
                if not DATABASE_PATH:
                    raise ValueError("DATABASE_PATH no está configurado en config.py")
                
                _engine = create_engine(f"sqlite:///{DATABASE_PATH}")
                print("⚠️ Conectando a SQLite local - DESARROLLO")
                
                # Solo crear tablas para SQLite local
                if not os.path.exists(DATABASE_PATH) or os.path.getsize(DATABASE_PATH) == 0:
                    print("🔧 Creando nueva base de datos local...")
                    Base.metadata.create_all(_engine)
                    print("✅ Tablas creadas exitosamente")
            
            _Session = sessionmaker(bind=_engine)
            print("✅ Base de datos inicializada correctamente")
            return True
            
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        _engine = None
        _Session = None
        return False
    
    return True

def get_db_session() -> SQLAlchemySession:
    """
    Devuelve una sesión SQLAlchemy lista para usar.
    
    Returns:
        SQLAlchemySession: Sesión de base de datos
        
    Raises:
        RuntimeError: Si no se puede inicializar la base de datos
    """
    global _Session
    
    # Asegurar que la base de datos esté inicializada
    if _Session is None:
        if not initialize_database():
            raise RuntimeError(
                "No se pudo inicializar la base de datos. "
                "Verifica que el archivo de configuración y los permisos sean correctos."
            )
    
    # Esta verificación nunca debería fallar después de initialize_database() exitoso,
    # pero la incluimos para satisfacer a Pylance
    if _Session is None:
        raise RuntimeError("Error crítico: _Session sigue siendo None después de la inicialización")
    
    return _Session()

def close_all_connections():
    """Cierra todas las conexiones y limpia los recursos globales."""
    global _engine, _Session
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
    
    _Session = None
    print("🔒 Conexiones de base de datos cerradas")

def get_database_info() -> dict:
    """
    Devuelve información sobre el estado de la base de datos.
    
    Returns:
        dict: Información sobre la base de datos
    """
    # 🔧 FIX: Validar DATABASE_PATH antes de usarlo
    if DATABASE_PATH is None:
        return {
            "database_path": "No configurado",
            "exists": False,
            "size_bytes": 0,
            "is_initialized": _Session is not None,
            "engine_active": _engine is not None,
            "error": "DATABASE_PATH no está configurado"
        }
    
    # Ahora DATABASE_PATH es válido (no None)
    return {
        "database_path": DATABASE_PATH,
        "exists": os.path.exists(DATABASE_PATH),
        "size_bytes": os.path.getsize(DATABASE_PATH) if os.path.exists(DATABASE_PATH) else 0,
        "is_initialized": _Session is not None,
        "engine_active": _engine is not None
    }