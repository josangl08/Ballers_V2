# controllers/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession
from models import Base
from config import DATABASE_URL, DATABASE_PATH, IS_PRODUCTION, IS_DEVELOPMENT
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
            # Usar DATABASE_URL ya procesado desde config.py
            print(f"🔗 Conectando a: {DATABASE_URL[:50]}...")
            
            _engine = create_engine(DATABASE_URL)
            
            # Solo crear tablas si es SQLite local Y no existe
            if IS_DEVELOPMENT and DATABASE_PATH:
                if not os.path.exists(DATABASE_PATH) or os.path.getsize(DATABASE_PATH) == 0:
                    print("🔧 Creando nueva base de datos local...")
                    Base.metadata.create_all(_engine)
                    print("✅ Tablas creadas exitosamente")
                else:
                    print("✅ Usando base de datos local existente")
            elif IS_PRODUCTION:
                print("✅ Conectado a base de datos de producción (Supabase)")
            
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
    info = {
        "database_url": DATABASE_URL[:50] + "..." if len(DATABASE_URL) > 50 else DATABASE_URL,
        "is_production": IS_PRODUCTION,
        "is_development": IS_DEVELOPMENT,
        "is_initialized": _Session is not None,
        "engine_active": _engine is not None
    }
    
    # Info adicional para desarrollo
    if IS_DEVELOPMENT and DATABASE_PATH:
        info["database_path"] = DATABASE_PATH
        info["exists"] = os.path.exists(DATABASE_PATH)
        info["size_bytes"] = os.path.getsize(DATABASE_PATH) if os.path.exists(DATABASE_PATH) else 0
    
    return info